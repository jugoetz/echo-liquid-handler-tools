#!/usr/bin/env python

"""
Generate the cherry-picking files for Labcyte Echo liquid handler

Inputs:
- Target plate layout files (csv):
    1 plate per file, multiple files possible, located in the eponymous folder by default

Outputs:
- Cherry-picking files (csv):
    1 file per step
- Source plate layout files (csv):
    1 file per source plate

Warning: The plate specification is currently hardcoded to 384well low dead volume Echo plates
"""

import sys
from globals import PKG_PATH
sys.path.insert(0, PKG_PATH)  # TODO get rid of this hack
from labware import plates
import os
import csv
import string
import argparse


def plate_to_dict(filename):
    """
    Import CSVs with plate layout (e.g. for 384 well plate) into a dictionary with wells as keys
    :param filename: str or list
    """
    if type(filename) == str:
        filename = [filename]
    well_dicts = {}
    for name, i in zip(filename, range(1, len(filename) + 1)):
        with open(name, 'r') as csvfile:
            reader = csv.reader(csvfile)
            # skip the first row (header, usually 1..16 or 1..24 for plates)
            next(reader)
            # generate dictionary from csv.reader iterator
            well_dicts[i] = {f'{row[0]}{element_nr}': row[element_nr]
                             for row in reader
                             for element_nr in range(1, len(row))
                             if row[element_nr] != ''  # skip all empty wells
                             }
    return well_dicts


def dict_to_plate(dictionary, filename_base, rows, columns, map):
    """
    Print a plate dictionary of the form {well: content} to a csv in plate format
    :param dictionary: dict
    :param filename_base: int
    :param columns: int
    :param map: dict
    :return: None
    """
    column_labels = [f'{i}' if i > 0 else '' for i in range(0, columns + 1)]
    for key, val in dictionary.items():
        with open(f'{filename_base}_{map[key]}.csv', 'w') as csvfile:
            writer = csv.writer(csvfile)
            # write header
            writer.writerow(column_labels)
            for r in range(1, rows + 1):
                row_letter = string.ascii_uppercase[r - 1]
                this_row = [row_letter]
                for c in range(1, columns + 1):
                    try:
                        this_row.append(val[f'{row_letter}{c}'])
                    except KeyError:
                        this_row.append('')
                writer.writerow(this_row)
    return


def generate_pipetting_pattern(source_dict, target_dict, transfers_per_source_well):
    pipetting_step_1 = []
    pipetting_step_2 = []
    source_loads = {i: dict.fromkeys(source_dict[i], transfers_per_source_well) for i in source_dict.keys()}  # count how many times the liquid handler can still take from any given source well
    # target_filled = {i: dict.fromkeys(target_dict[i], [False, False, False]) for i in target_dict.keys()}

    for target_plate_key, target_plate_val in target_dict.items():  # iterate all target plates
        for target_well_key, target_well_val in target_plate_val.items():  # iterate all target wells
            for compound in target_well_val.split(','):  # iterate all compounds in any target well
                compound = compound.strip()

                for source_plate_key, source_plate_val in source_dict.items():  # iterate all source plates
                    for source_well_key, source_well_val in source_plate_val.items():  # iterate all source wells
                        if compound in source_well_val and source_loads[source_plate_key][source_well_key] > 0:  # check if required compound is in the source well AND if there is still a load left for transferring
                            source_loads[source_plate_key][source_well_key] -= 1  # deplete one load from source well
                            if 'I' in compound or 'M' in compound:  # add to step 1 if I or M
                                pipetting_step_1.append(
                                    [source_plate_key, source_well_key, target_plate_key, target_well_key])
                            elif 'T' in compound:  # add to step 2 if T
                                pipetting_step_2.append(
                                    [source_plate_key, source_well_key, target_plate_key, target_well_key])
                            else:
                                print(f'ERROR. Encountered unknown compound "{compound}"')
                            break  # break out of the source well loop when transfer step has been found
                    else:
                        continue  # go to next iteration of outer for-loop without breaking
                    break  # (only executed if else statement is not hit) break the source plate loop as well

    # sort the pipetting step lists so that one target plate is filled first with I, then M, then next target plate is filled
    # (minimum number of plate changes)
    pipetting_step_1.sort(key=lambda x: x[0])  # sort by source plate
    pipetting_step_1.sort(key=lambda x: x[2])  # sort by target plate
    pipetting_step_2.sort(key=lambda x: x[2])  # for step 2 sorting by target plate suffices

    print('\n#### Transfer operations:')
    print(f'Step 1: {pipetting_step_1}')
    print(f'Total of {len(pipetting_step_1)} operations')
    print(f'Step 2: {pipetting_step_2}')
    print(f'Total of {len(pipetting_step_2)} operations')
    return pipetting_step_1, pipetting_step_2


def dict_to_cherrypickfile(transfers, filename, vol, map):
    """
    generate cherry picking file output
    :param transfers: list of 4-tuples [(source plate, source well, target plate, target well),...]
    :param filename: str
    :param vol: int or float, note that input is [µL] whereas [nL] will be printed to the cherrypickfile
    :param map: dict, mapping the names of plates to numbers
    :return: None
    """
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        # write header
        writer.writerow(['Source Barcode', 'Source Well', 'Destination Barcode', 'Destination Well', 'Volume'])
        # write transfers
        for t in transfers:
            writer.writerow([f'Source{map[t[0]]}', t[1], f'Synthesis{t[2]}', t[3], str(vol * 1000)])
    return


if __name__ == '__main__':
    """defaults"""
    target_dir_default = 'target_plate_layouts'
    file_source_plate_base = 'source'
    cherry_pick_file_1 = 'step1.csv'
    cherry_pick_file_2 = 'step2.csv'
    source_well_max_volume = 65000  # nL
    source_well_dead_volume = 15000  # nL
    source_n_columns = 24
    source_n_rows = 16
    target_well_max_volume = 12000  # nL
    target_well_dead_volume = 2500  # nL
    target_n_columns = 24
    target_n_rows = 16

    transfer_volume = 1100  # volume [nL] of building block solution used per filled target well
    building_blocks = ['I', 'M', 'T']

    source_n_wells = source_n_rows * source_n_columns

    """parse sys args"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', nargs='*', help='filenames of the target plate layout files')
    args = vars(parser.parse_args())
    target_files = args['f']

    """check if user gave custom input file location"""
    if target_files:
        # ensure this will be a list, even with only one element
        if type(target_files) == str:
            file_target_plates = [target_files, ]
        else:
            file_target_plates = target_files
    else:
        # use default location
        file_target_plates = []
        for root, _, files in os.walk(target_dir_default):
            for f in files:
                if not f.endswith('_volumes.csv'):  # filter volume files
                    file_target_plates.append(os.path.join(root, f))
    print(f'Importing files {file_target_plates}...')

    """import target plates"""
    target_plates = []
    for i, file in enumerate(file_target_plates):
        target_plates.append(plates.Plate(target_n_rows,
                                          target_n_columns,
                                          target_well_max_volume,
                                          target_well_dead_volume
                                          ))  # generate the Plate instance to hold the data
        target_plates[i].from_csv(file, vol=3300)
        target_plates[i].to_csv(file, True)

    print(f'Target plates:')
    for p in target_plates:
        print(p)

    """calculate number of wells in source plate for every building block"""
    usage = {}
    for plate in target_plates:
        for well in plate.wells():
            compounds, volume = plate.well(well)
            for compound in compounds:
                try:
                    usage[compound] += volume // len(compounds)  # we use floor division as we deal with int nL values
                except KeyError:  # raised if this is the first time this building block is encountered
                    usage[compound] = volume // len(compounds)
    print(f'Usage counter: {usage}')
    wells_per_bb = {key: val // (source_well_max_volume - source_well_dead_volume) + 1 for key, val in usage.items()}

    """sort the dict of required source wells: 1st sort by building block number, then sort by type"""
    wells_per_bb = dict(sorted(wells_per_bb.items(), key=lambda item: int(item[0][1:])))
    wells_per_bb = dict(sorted(wells_per_bb.items(), key=lambda item: item[0][:1]))
    print(f'Wells needed per BB: {wells_per_bb}')

    source_plates = []
    finished = False
    i = 0
    while finished is False:
        source_plates.append(plates.Plate(source_n_rows,
                                          source_n_columns,
                                          source_well_max_volume,
                                          source_well_dead_volume
                                          ))
        # TODO go on here
        plate = source_plates[i]
        for key, val in wells_per_bb.values():
            plate.free()
    """check if building blocks fit one plate"""
    sum_bb = sum(wells_per_bb.values())
    if sum_bb <= source_n_wells:
        n_sources = 1  # use one source plate
    elif sum_bb <= source_n_wells * len(building_blocks):
        n_sources = len(building_blocks)  # use one plate per building block
    else:
        raise NotImplementedError('Cannot exceed one source plate per building block')

    """generate source plate layouts"""
    source = {}
    success = False
    if n_sources == 1:
        wells = {}
        wells['I'] = (f'{row}{column + 1}' for row in string.ascii_uppercase[0:n_rows // 3] for column in range(n_columns))
        wells['M'] = (f'{row}{column + 1}' for row in string.ascii_uppercase[n_rows // 3: 2 * n_rows // 3] for column in range(n_columns))
        wells['T'] = (f'{row}{column + 1}' for row in string.ascii_uppercase[2 * n_rows // 3:n_rows] for column in range(n_columns))
        """
        The following assignment may still error due to the division of the plate into thirds.
        E.g. if there are 200 of one building block and only 50 of the two other building blocks for a 384 well plate,
        this will error.
        We catch this with try-except and let it use separate plates for the building blocks instead
        """
        try:
            for bb in building_blocks:
                for key, val in wells_per_bb.items():
                    if key.startswith(bb):
                        while val > 0:
                            source[next(wells[bb])] = key
                            val -= 1
            print(f'Source plate: {source}')
            source = {0: source}
            source_plate_nr = 1
            success = True
        except StopIteration:
            pass
    if not success:
        # when building blocks don't fit one source plate (generator object running out of free wells)
        source_plate_nr = 3
        for bb in building_blocks:
            wells = (f'{row}{column + 1}' for row in string.ascii_uppercase[0:n_rows] for column in range(n_columns))  # new plate for every building block
            source[bb] = {}  # separate dictionary for every source plate
            for key, val in wells_per_bb.items():
                if key.startswith(bb):
                    while val > 0:  # while more wells are needed for specific building block
                        source[bb][next(wells)] = key
                        val -= 1
    """map plate names to numbers"""
    map = {let: num+1 for num, let in enumerate(source.keys())}
    """generate pipetting pattern"""
    step_1, step_2 = generate_pipetting_pattern(source, dict_targets, transfers_per_well)

    """output to file"""
    dict_to_cherrypickfile(step_1, cherry_pick_file_1, transfer_volume, map)
    dict_to_cherrypickfile(step_2, cherry_pick_file_2, transfer_volume, map)
    dict_to_plate(source, file_source_plate_base, n_rows, n_columns, map)
