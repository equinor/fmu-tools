

class QCForward(object):

    def __init__(self):
        self._name = None
        self._whatever = None


    def wellzonation_vs_grid(
        self,
        gridfile=None,
        zonefile=None,
        rmsproject=None,
        gridname=None
    ):
        """Check well zonation or perforations vs 3D grid."""
        print("Testing")

        print(gridfile, zonefile, rmsproject, gridname)
