# -*- coding: utf-8 -*-
"""Script for generating a design matrix from config input"""

from __future__ import division, print_function, absolute_import

import argparse
import sys
import os.path

from fmu.tools.sensitivities import DesignMatrix, excel2dict_design


def _do_parse_args(args):

    if args is None:
        args = sys.argv[1:]
    else:
        args = args

    usetxt = 'fmudesign ...'

    parser = argparse.ArgumentParser(
        description='Generate design matrix to be used with ert DESIGN2PARAMS',
        usage=usetxt
    )

    # positional:
    parser.add_argument('config',
                        type=str,
                        help=('Input design config filename '
                              'on Excel format'))

    parser.add_argument('destination',
                        type=str,
                        help='Destination folder for design matrix')

    if len(args) < 2:
        parser.print_help()
        print('QUIT')
        raise SystemExit

    args = parser.parse_args(args)
    return args


def main(args=None):
    """fmudesign is a script that takes ..."""

    args = _do_parse_args(args)

    if isinstance(args.config, str):
        if not os.path.isfile(args.config):
            raise IOError('Input file does not exist')
        input_dict = excel2dict_design(args.config)

    design = DesignMatrix()

    design.generate(input_dict)

    folder = os.path.dirname(args.destination)

    if not os.path.exists(folder) and folder != '':
        raise ValueError('Folder "{}" for output file '
                         'does not exist.'
                         'Create in advance'.format(folder))

    design.to_xlsx(args.destination)


if __name__ == '__main__':
    main()
