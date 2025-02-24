import numpy as np

from tf_keras.callbacks import TensorBoard
import tensorflow as tf
from tf_keras.models import Model, load_model
from tf_keras.layers import Input, BatchNormalization, Activation, Dense, Dropout, Cropping2D
from tf_keras.layers.core import Reshape
from tf_keras.layers.convolutional import Conv2D, Conv2DTranspose
from tf_keras.layers.pooling import MaxPooling2D
from tf_keras.layers.merge import concatenate, add
from tf_keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from tf_keras.optimizers import Adam
from tf_keras import backend as K
from tf_keras.preprocessing.image import ImageDataGenerator


def conv2d_block(input_tensor, n_filters, kernel_size=3):
    # first layer
    x = Conv2D(filters=n_filters, kernel_size=(kernel_size, kernel_size),
               padding="same")(input_tensor)
    x = Activation("relu")(x)
    # second layer
    x = Conv2D(filters=n_filters, kernel_size=(kernel_size, kernel_size), 
               padding="same")(x)
    x = Activation("relu")(x)
    return x


def get_unet(input_img, n_filters, target_shape):
    # contracting path
    c1 = conv2d_block(input_img, n_filters=n_filters*4, kernel_size=3) #The first block of U-net
    p1 = MaxPooling2D((2, 2)) (c1)

    c2 = conv2d_block(p1, n_filters=n_filters*8, kernel_size=3)
    p2 = MaxPooling2D((2, 2)) (c2)

    c3 = conv2d_block(p2, n_filters=n_filters*16, kernel_size=3)
    p3 = MaxPooling2D((2, 2)) (c3)

    c4 = conv2d_block(p3, n_filters=n_filters*32, kernel_size=3)
    p4 = MaxPooling2D(pool_size=(2, 2)) (c4)
    
    c5 = conv2d_block(p4, n_filters=n_filters*64, kernel_size=3)
     
    # expansive path
    u6 = Conv2DTranspose(n_filters*32, (3, 3), strides=(2, 2), padding='same') (c5)
    u6 = concatenate([u6, c4])
    c6 = conv2d_block(u6, n_filters=n_filters*32, kernel_size=3)

    u7 = Conv2DTranspose(n_filters*16, (3, 3), strides=(2, 2), padding='same') (c6)
    u7 = concatenate([u7, c3])
    c7 = conv2d_block(u7, n_filters=n_filters*16, kernel_size=3)

    u8 = Conv2DTranspose(n_filters*8, (3, 3), strides=(2, 2), padding='same') (c7)
    u8 = concatenate([u8, c2])
    c8 = conv2d_block(u8, n_filters=n_filters*8, kernel_size=3)

    u9 = Conv2DTranspose(n_filters*4, (3, 3), strides=(2, 2), padding='same') (c8)
    u9 = concatenate([u9, c1], axis=3)
    c9 = conv2d_block(u9, n_filters=n_filters*4, kernel_size=3)
    
    outputs = Conv2D(1, (1, 1), activation='sigmoid') (c9)
    model = Model(inputs=[input_img], outputs=[outputs])
    return model


def dice_coefficient(y_true, y_pred):
    eps = 1e-6
    y_true_f = K.flatten(y_true)
    y_pred_f = K.flatten(y_pred)
    intersection = K.sum(y_true_f * y_pred_f)
    return (2. * intersection) / (K.sum(y_true_f * y_true_f) + K.sum(y_pred_f * y_pred_f) + eps)


def neg_dice_coefficient(y_true, y_pred):
    eps = 1e-6
    y_true_f = K.flatten(y_true)
    y_pred_f = K.flatten(y_pred)
    intersection = K.sum(y_true_f * y_pred_f)
    return -((2. * intersection) / (K.sum(y_true_f * y_true_f) + K.sum(y_pred_f * y_pred_f) + eps))


class IDGWithLabels():
    """
    Extension of Keras' ImageDataGenerator that allows flipping/rotating the labels as well.
    Kwargs are forwarded to the ImageDataGenerator.
    """
    def __init__(self, flip=True, rot90=True, **kwargs):
        self.generator = ImageDataGenerator(**kwargs)
        self.flip = flip
        self.rot90 = rot90

    def flow(self, *args, **kwargs):
        for X, y in self.generator.flow(*args, **kwargs):
            if self.flip:
                k = np.random.binomial(1, 0.5, size=2) * 2 - 1
                X = X[:, ::k[0], ::k[1]]
                y = y[:, ::k[0], ::k[1]]

            if self.rot90:
                k = np.random.randint(4)
                X = np.rot90(X, k, (1, 2))
                y = np.rot90(y, k, (1, 2))

            yield X, y