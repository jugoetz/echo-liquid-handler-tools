#!/usr/bin/env python

"""
Generate the cherry-picking files for Labcyte Echo liquid handler

Inputs:
- Target plate layout files (csv):
    1 plate per file

Outputs:
- Cherry-picking files (csv):
    1 file per step
- Source plate layout file (csv):
"""

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


def dict_to_cherrypickfile(dictionary, filename, vol):
    """
    generate cherry picking file output
    :param dictionary: dict
    :param filename: str
    :param vol: int
    :return: None
    """
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        # write header
        writer.writerow(['Source Barcode', 'Source Well', 'Destination Barcode', 'Destination Well', 'Volume'])
        for i in dictionary:
            writer.writerow(['Source1', i[0], f'Synthesis{i[2]}', i[1], str(vol)])
    return


def dict_to_plate(dictionary, filename, rows, columns):
    """
    Print a plate dictionary of the form {well: content} to a csv in plate format
    :param dictionary: dict
    :param filename: str
    :param rows: int
    :param columns: int
    :return: None
    """
    column_labels = [f'{i}' if i > 0 else '' for i in range(0, columns + 1)]
    with open(filename, 'w') as csvfile:
        writer = csv.writer(csvfile)
        # write header
        writer.writerow(column_labels)
        for r in range(1, rows + 1):
            row_letter = string.ascii_uppercase[r - 1]
            this_row = [row_letter]
            for c in range(1, columns + 1):
                try:
                    this_row.append(dictionary[f'{row_letter}{c}'])
                except KeyError:
                    this_row.append('')
            writer.writerow(this_row)
    return


if __name__ == '__main__':
    # parse sys args
    # TODO add the filenames as sys args?
    parser = argparse.ArgumentParser()
    parser.add_argument('number', type=int, help='number of target plates')
    args = parser.parse_args()
    target_nr = args.number

    # inputs
    file_target_plates = [f'sample data/plate_layout_plate{i+1}.csv' for i in range(target_nr)]
    print(f'Importing files {file_target_plates}')

    # outputs
    file_source_plate = 'source.csv'
    cherry_pick_file_1 = 'step1.csv'
    cherry_pick_file_2 = 'step2.csv'

    # specify source plate
    source_well_volume = 50  # usable volume [µL] of every well (total volume - dead volume)
    transfer_volume = 1  # volume [µL] of building block solution used per filled target well
    columns = 24  # WE ASSUME THAT A 384 WELL PLATE IS USED.
    rows = 16

    # import
    dict_targets = plate_to_dict(file_target_plates)
    print(f'Target plates: {dict_targets}')

    # count building block usage
    counter = {}
    for i in range(1, target_nr+1):
        for val in dict_targets[i].values():
            for i in val.split(','):
                try:
                    counter[i.strip()] += 1
                except KeyError:
                    counter[i.strip()] = 1
    print(f'Usage counter: {counter}')

    # calculate number of wells in source plate
    transfers_per_well = source_well_volume // transfer_volume
    wells_per_BB = {key: val // transfers_per_well + 1 for key, val in counter.items()}

    # sort the dict of required source wells: 1st sort by building block number, then sort by type
    wells_per_BB = dict(sorted(wells_per_BB.items(), key=lambda item: int(item[0][1:])))
    wells_per_BB = dict(sorted(wells_per_BB.items(), key=lambda item: item[0][:1]))
    print(f'Wells needed per BB: {wells_per_BB}')

    # generate the plate layout for the source plate
    source = {}
    wells = {}
    wells['I'] = (f'{row}{column + 1}' for row in string.ascii_uppercase[0:rows // 3] for column in range(columns))
    wells['M'] = (f'{row}{column + 1}' for row in string.ascii_uppercase[rows // 3: 2 * rows // 3] for column in range(columns))
    wells['T'] = (f'{row}{column + 1}' for row in string.ascii_uppercase[2 * rows // 3:rows] for column in range(columns))
    # Now this might error if the building blocks don't fit one source plate
    for bb in ['I', 'M', 'T']:
        for key, val in wells_per_BB.items():
            if key.startswith(bb):
                while val > 0:
                    source[next(wells[bb])] = key
                    val -= 1
    print(f'Source plate: {source}')

    # generate pipetting pattern
    pipetting_step_1 = []
    pipetting_step_2 = []
    for key, val in source.items():
        for i in range(1, target_nr + 1):
            for target_key, target_val in dict_targets[i].items():
                if val in target_val:
                    if 'I' in val or 'M' in val:
                        pipetting_step_1.append([key, target_key, i])
                    elif 'T' in val:
                        pipetting_step_2.append([key, target_key, i])
                    else:
                        print(f'ERROR. Encountered unknown reactant type {val}')

    print(f'Step 1: {pipetting_step_1}')
    print(f'Step 2: {pipetting_step_2}')

    # output to file
    dict_to_cherrypickfile(pipetting_step_1, cherry_pick_file_1, transfer_volume)
    dict_to_cherrypickfile(pipetting_step_2, cherry_pick_file_2, transfer_volume)
    dict_to_plate(source, file_source_plate, rows, columns)
