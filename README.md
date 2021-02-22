## Echo cherry-picking tool (_in development_)

The tools intent is to generate transfer files for the Echo liquid handler based on a desired target plate layout.

### Usage
One or more layout files for the target plate(s) must be provided either in the default target_plate_layouts folder 
or at a location specified when calling the script from the command line.
The specifications for source plates (plate format, well volume), the building block types, and the volume per building 
block are currently hardcoded into the script (TODO overwrite defaults with argparse).

### Current limitations

- A maximum of 3 source plates is implemented
- The names of the building blocks ("I", "M", "T") are partially hardcoded into the script
