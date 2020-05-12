# tomo-spectrum-matcher

Utility to normalize CryoET data by matching amplitude spectrums.

Currently it consists of two main components: 
- Extraction of a tomogram's radially averaged amplitude spectrum
- Applying an extracted spectrum to other tomograms


## Installation
- Install [Miniconda3](https://docs.conda.io/en/latest/miniconda.html)
- Clone the git repo
- Create a new conda environment and activate it
```bash
    $ conda env create -f requirements.yaml
    $ conda activate tsm
```
- Done!

## Usage
### Extracting an amplitude spectrum
To extract a tomogram's amplitude spectrum:  
```bash 
$ python extract_spectrum.py --input <input_tomo.mrc> --output <amp_spectrum.tsv>
```

### Match a tomogram to an extracted spectrum
To apply an extracted amplitude spectrum to another tomogram:  
```bash
$ python match_spectrum.py --input <imput_tomo.mrc> --target <amp_spectrum.tsv> --output <filtered_tomo.mrc>
```

## TO DO
- Add detailed algorithm explanation to README
