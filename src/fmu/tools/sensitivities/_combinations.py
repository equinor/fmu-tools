# -*- coding: utf-8 -*-
""" Module with support tools for singlesens"""


def find_combinations(selections):
    """
    :returns: A list of all possible combinations of the chosen selections
    :param selections: ordered dictionary where each key (selector) is
     a string and the value (filtering choices for this selector)
     is a list of lists
    :Example:

    >>> from collections import OrderedDict
    >>> exampleinput = {'numbers': ['one', 'two', 'three'],
                        'letters': ['a', 'b']}
    >>> find_combinations(exampleinput)
    [['one', 'a'],
    ['two', 'a'],
    ['three', 'a'],
    ['one', 'b'],
    ['two', 'b'],
    ['three', 'b']]

    """
    # create list of lists with values from dictionary
    values = []
    for item in range(len(selections)):
        values.append(selections.values()[item])

    # find all possible combinations
    combinations = [[]]
    for xitem in values:
        tempcomb = []
        for yitem in xitem:
            for combitem in combinations:
                tempcomb.append(combitem+[yitem])
        combinations = tempcomb

    return combinations
