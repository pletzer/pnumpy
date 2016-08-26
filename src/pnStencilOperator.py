#!/usr/bin/env python

"""
Apply stencil to distributed array data
"""

# external dependencies
from mpi4py import MPI
import numpy

# internal dependencies
from pnumpy import daZeros
from pnumpy import Partition
from pnumpy import MultiArrayIter
from pnumpy import DomainPartitionIter
from pnumpy import CubeDecomp


class StencilOperator:

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
        self.myRank = comm.Get_rank()
        self.comm = comm
        self.decomp = decomp
        self.periodic = periodic

        # defaul stencil is empty
        self.stencil = {}

        # partition logic, initially empty
        self.dpis = {}

    def addStencilBranch(self, disp, weight):
        """
        Set or overwrite the stencil weight for the given direction
        @param disp displacement vector
        @param weight stencil weight
        """
        self.stencil[disp] = weight
        self.__setPartionLogic(disp)

    def removeStencilBranch(self, disp):
        """
        Remove a stencil branch
        @param disp displacement vector
        """
        del self.stencil[disp]
        del self.dpsi[disp]

    def __setPartionLogic(self, disp):

        sdisp = str(disp)

        srcDp = DomainPartitionIter(disp)
        dstDp = DomainPartitionIter([-d for d in disp])

        srcs = [d.getPartition().getSlice() for d in srcDp]
        dsts = [d.getPartition().getSlice() for d in dstDp]

        srcDp.reset()
        remoteRanks = [self.decomp.getNeighborProc(self.myRank, part.getDirection(), 
                                                   periodic=self.periodic) \
                       for part in srcDp]
            
        srcDp.reset()
        remoteWinIds = [sdisp + '[' + part.getStringPartition() + ']' \
                        for part in srcDp]

        self.dpis[disp] = {
            'srcs': srcs,
            'dsts': dsts,
            'remoteRanks': remoteRanks,
            'remoteWinIds': remoteWinIds,
        }
        print('>>> [{0}] remoteRanks = {1}'.format(self.myRank, remoteRanks))
        print('>>> [{0}] self.decomp.getNeighborProc(self.myRank, (1,), self.periodic) = {1}'.format(self.myRank, self.decomp.getNeighborProc(self.myRank, (1,), self.periodic)))

    def apply(self, localArray):
        """
        Apply stencil to data
        @param localArray local array
        @return new array on local proc
        """

        # input dist array
        inp = daZeros(localArray.shape, localArray.dtype)
        inp.setComm(self.comm)

        # output array
        out = numpy.zeros(localArray.shape, localArray.dtype)

        # expose the dist array windows
        for disp, dpi in self.dpis.items():

            sdisp = str(disp)

            srcs = dpi['srcs']
            remoteWinIds = dpi['remoteWinIds']
            numParts = len(srcs)
            for i in range(numParts):
                print('--- [{0}] exposing window id = {1}'.format(self.myRank, remoteWinIds[i]))
                inp.expose(srcs[i], winID=remoteWinIds[i])

        # apply the stencil
        for disp, weight in self.stencil.items():

            dpi = self.dpis[disp]

            dpi = self.dpis[disp]

            srcs = dpi['srcs']
            dsts = dpi['dsts']
            remoteRanks = dpi['remoteRanks']
            remoteWinIds = dpi['remoteWinIds']
            numParts = len(srcs)
            for i in range(numParts):
                srcSlce = srcs[i]
                dstSlce = dsts[i]
                remoteRank = remoteRanks[i]
                remoteWinId = remoteWinIds[i]

                # now apply the stencil
                print('.... [{0}] apply stencil for dstSlce = {1} weight={2} remoteRank={3}'.format(self.myRank, dstSlce, weight, remoteRank))
                out[dstSlce] += weight * inp.getData(remoteRank, remoteWinId)

        # some implementations require this
        inp.free()

        return out

##############################################################################


def test1d():
    rk = MPI.COMM_WORLD.Get_rank()
    sz = MPI.COMM_WORLD.Get_size()
    dims = (3,)
    globalDims = (3*sz,)
    decomp = CubeDecomp(nprocs=sz, dims=globalDims)
    so = StencilOperator(decomp, periodic=[True])
    so.addStencilBranch((1,), 2.0)
    inputData = (rk + 1) * numpy.ones(dims, numpy.float32)
    outputData = so.apply(inputData)
    print('[{0}] inputData = {1}'.format(rk, inputData))
    print('[{0}] outputData = {1}'.format(rk, outputData))


if __name__ == '__main__':
    test1d()