#/usr/bin/env python

"""
Apply Laplacian stencil to distributed array data
"""

import copy

# external dependencies
from mpi4py import MPI
import numpy
from pnumpy import gdaZeros, gmdaZeros, Partition

class Laplacian:

    def __init__(self, decomp, periodic=None, comm=MPI.COMM_WORLD):
        """
        Constructor
        @param decomp instance of setCubeDecomp
        @param periodic list of True/False values (True for periodic)
        @param comm MPI communicator
        """
        # number of dimensions
        self.ndims = decomp.getNumDims()

        # this process's MPI rank
        myRank = comm.Get_rank()

        # zero displacement vector
        self.zeros = tuple([0] * self.ndims)

        # set the laplacian stencil weights
        self.stencil = {
            self.zeros: -2.0 * self.ndims,
            }
        for drect in range(self.ndims):
            for pm in (-1, 1):
                disp = [0] * self.ndims
                disp[drect] = pm
                self.stencil[tuple(disp)] = 1.0

        #
        # build the domain partitioning/topology data structures, all
        # of these take the displacement vector as input
        #
        # entire domain
        self.domain = Partition(self.ndims)

        # the local domain of the input array
        self.srcLocalDomains = {}
        # the local domain of the output array
        self.dstLocalDomains = {}

        # the side domain on the neighbor rank
        self.srcSlab = {}
        # the side domain on the receiving end
        self.dstSlab = {}

        # the window Ids
        self.winIds = {}

        # the neighbor rank 
        self.neighRk = {}

        for drect in range(self.ndims):
            for pm in (-1, 1):
                disp = [0] * self.ndims; disp[drect] = pm
                negDisp = [0] * self.ndims; negDisp[drect] = -pm
                disp = tuple(disp)
                negDisp = tuple(negDisp)
                self.srcLocalDomains[disp] = self.domain.shift(disp).getSlice()
                self.dstLocalDomains[disp] = self.domain.shift(negDisp).getSlice()
                self.srcSlab[disp] = self.domain.extract(negDisp).getSlice()
                self.dstSlab[disp] = self.domain.extract(disp).getSlice()

                # assumes disp only contains -1, 0s, or 1
                self.neighRk[disp] = decomp.getNeighborProc(myRank, disp, periodic=periodic)

                self.winIds[disp] = negDisp

    def apply(self, localArray):
        """
        Apply Laplacian stencil to data
        @param localArray local array
        @return new array on local proc
        """

        # input dist array
        inp = gdaZeros(localArray.shape, localArray.dtype)
        # output dist array
        out = gdaZeros(localArray.shape, localArray.dtype)

        # no displacement term
        weight = self.stencil[self.zeros]
        out[...] += weight * localArray

        for disp in self.srcLocalDomains:

            weight = self.stencil[disp]

            # no communication required here
            srcDom = self.srcLocalDomains[disp]
            dstDom = self.dstLocalDomains[disp]
            out[dstDom] += weight * localArray[srcDom]

            #
            # now the part that requires communication
            #

            # set the ghost values
            srcSlab = self.srcSlab[disp]
            inp[srcSlab] = localArray[srcSlab] # copy

            # send over to local process
            dstSlab = self.dstSlab[disp]
            winId = self.winIds[disp]
            rk = self.neighRk[disp]
            out[dstSlab] += weight * inp.getData(rk, winId)

        return out[...]


######################################################################

def test1d():

    import sys
    from pnCubeDecomp import CubeDecomp

    # number of procs
    sz = MPI.COMM_WORLD.Get_size()
    # MPI rank
    rk = MPI.COMM_WORLD.Get_rank()

    # domain decomp
    n0 = 8
    dc = CubeDecomp(sz, (n0,))
    if not dc.getDecomp():
        print('*** ERROR Invalid domain decomposition -- rerun with different sizes/number of procs')
        sys.exit(1)

    lapl = Laplacian(dc, periodic=(True,))
    ii = numpy.arange(0, n0) + 0.5
    xx = ii/float(n0)
    inp = 0.5 * xx**2
    out = lapl.apply(inp)
    print(out)


if __name__ == '__main__': 
    test1d()
