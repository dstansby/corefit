This folder contains the code that generates the corefit dataset from the
original distribution function files.

The following steps can be used to download the code, original data files, and
required dependencies.

Downloading and installing software
-----------------------------------
1. Download a copy of this repository
2. Install [python](https://www.python.org/)
3. Install the required python dependencies by running
`pip install -r requirements.txt` from the `corefit` directory

Configuring data output
-----------------------
In the `corefit` directory, change the name of
`config.ini.template` to `config.ini` and fill in the directory where you
would like the output data to be saved to

Downloading original data files
-------------------------------
1. Create a directory to store all of the original magnetic field and
distribution function data files.
2. Configure heliopy to look in this location for the data files. Create
a heliopyrc file using
```bash
mkdir ~/.heliopy
echo "download_dir = /data/storage/directory" >> ~/.heliopy/heliopyrc
```
(replacing "/data/storage/directory" by the directory where all the data will
be stored)

3. Download the original distribution function files from ftp://apollo.ssl.berkeley.edu/pub/helios-data/E1_experiment/helios_original/
The directory structure in your download location needs changing a bit,
and should look like (1974 is an example year, 44 is an example day of year)
```bash
/data/storage/directory/helios/helios1/dist/1974/44/...
```
If you only want to regenerate specific days of data, you only need to download
the relevant files and not the entire dataset.

4. Download the 4Hz magnetic field data from ftp://apollo.ssl.berkeley.edu/pub/helios-data/E2_experiment/Data_Cologne_Nov2016_bestdata/HR/
The directory structure in your download location needs changing a bit,
and should look like
```bash
/data/storage/directory/helios/helios1/mag/4hz/
```
with all the files (for helios 1) stored in this directory.

5. Download the 6s magnetic field data from
ftp://apollo.ssl.berkeley.edu/pub/helios-data/E3_experiment/
The directory structure in your download location needs changing a bit,
and should look like (1974 is an example year, 44 is an example day of year)
```bash
/data/storage/directory/helios/helios1/6sec_ness/1974/
```
with all the files (in this example for helios 1 in 1974) in this directory.

**The distribution function files, 4Hz magnetic field data, and
6s magnetic field are all needed to regenerate the corefit dataset**


Regenerating the corefit dataset
--------------------------------
The corefit data set can now be re-generated by changing to the
`corefit` directory and running

```bash
python fitting/save_dist_params.py
```

This will generate the data set in *.hdf* files, which are easily read by python.
To clean and convert the files to ascii *.csv* files run

```bash
python fitting/convert_distparams.py
```
