"""
The module related to the VCI class for Vibrational Configuration Interaction calculations
"""

import numpy as np
import Misc


class VCI:
    """
    The class performing and storing VCI calculations
    """
    def __init__(self, grids, wavefunctions, *potentials):
        """
        The class must be initialized with grids, some, e.g. VSCF, wave functions, and potentials

        @param grids: The object containing the grids
        @type grids: Vibrations/Grid
        @param wavefunctions: The object containing the reference wave function, e.g. VSCF wfn
        @type wavefunctions: Vibrations/Wavefunction
        @param *potentials: The potentials
        @type *potentials: Vibrations/Potential
        """

        self.grids = grids.grids  # TODO this must be done with some method like grids.get_grids() or so
        self.wfns = wavefunctions.wfns  # these are VSCF optimized wave functions TODO must be done as above

        self.nmodes = grids.nmodes
        self.ngrid = grids.ngrid

        self.states = []
        self.solved = False

        self.dx = [x[1]-x[0] for x in self.grids]
        self.a = [(0.7**2.0)/((x[1]-x[0])**2.0) for x in self.grids]

        self.coefficients = np.zeros((self.nmodes, self.ngrid, self.ngrid))  # TODO number of VSCF states in wfn
        self._calculate_coeff()

        self.sij = np.zeros((self.nmodes, self.ngrid, self.ngrid))  # calculate Sij only once
        self._calculate_ovrlp_integrals()

        self.tij = np.zeros((self.nmodes, self.ngrid, self.ngrid))  # calculate Tij only once as well
        self._calculate_kinetic_integrals()

        self.energies = np.array([])
        self.energiesrcm = np.array([])
        self.vectors = np.array([])

        if len(potentials) != 2:
            raise Exception('Only two potentials, V1 and V2, accepted, so far')
        else:
            self.v1 = potentials[0].pot
            self.v2 = potentials[1].pot

        self.dm1 = np.array([])
        self.dm2 = np.array([])

        # TODO
        # 1. Check shapes of data stored in objects

    def solve(self):
        """
        Runs the VCI calculations
        """
        import itertools

        if len(self.states) == 0:
            print Misc.fancy_box('No CI space defined, by default singles space will be used')
            self.generate_states()

        # generate combination of states
        comb = [x for x in itertools.combinations_with_replacement(self.states, 2)]

        ncomb = len(comb)

        print Misc.fancy_box('Number of combinations : '+str(ncomb))

        # hamiltonian

        hamiltonian = np.zeros((len(self.states), len(self.states)))
        counter = 0

        for i in range(ncomb):
            counter += 1

            tmp = 0.0  # matrix element

            n = comb[i][0]  # left state
            m = comb[i][1]  # right state
            print 'Working on configuration %i out of %i' % (i+1, ncomb)
            print ' < %s | H | %s >' % (str(n), str(m))

            # 1-mode integrals
            for j in range(self.nmodes):
                tmpovrlp = 1.0
                tmpv1 = 0.0
                tmpt = 0.0

                for k in range(self.nmodes):

                    if k == j:
                        tmpv1 = self._v1_integral(j, n[j], m[j])
                        tmpt = self._kinetic_integral(j, n[j], m[j])

                    else:
                        if n[k] == m[k]:
                            s = self._ovrlp_integral(k, n[k], n[k])
                            tmpovrlp *= s

                        else:
                            tmpovrlp = 0.0

                tmpv1 *= tmpovrlp
                tmpt *= tmpovrlp

                tmp += tmpv1 + tmpt
            # 2-mode integrals
            for j in range(self.nmodes):

                for k in range(j+1, self.nmodes):
                    tmpovrlp = 1.0
                    tmpv2 = self._v2_integral(j, k, n[j], n[k], m[j], m[k])

                    for l in range(self.nmodes):

                        if l != j and l != k:
                            if n[l] == m[l]:

                                tmpovrlp *= self._ovrlp_integral(l, n[l], n[l])

                            else:
                                tmpovrlp = 0.0

                    tmpv2 *= tmpovrlp

                    tmp += tmpv2
            nind = self.states.index(n)  # find the left state in the states vector
            mind = self.states.index(m)  # fin the right state
            hamiltonian[nind, mind] = tmp

            print 'Step %i/%i done, value %f stored' % (counter, ncomb, tmp)

        print Misc.fancy_box('Hamiltonian matrix constructed. Diagonalization...')
        w, v = np.linalg.eigh(hamiltonian, UPLO='U')

        self.energies = w
        self.vectors = v
        wcm = w / Misc.cm_in_au
        self.energiesrcm = wcm  # energies in reciprocal cm
        print 'State %15s %15s' % ('E /cm^-1', 'DE /cm^-1')
        for i in range(len(self.states)):
            print "%s %10.4f %10.4f" % (self.states[i], wcm[i], wcm[i]-wcm[0])

        self.solved = True

    def print_states(self):
        """
        Prints the vibrational states used in the VCI calculations
        """
        print ''
        print Misc.fancy_box('CI Space')
        print self.states

    def generate_states(self, maxexc=1):
        """
        Generates the states for the VCI calcualtions

        @param maxexc: Maximal excitation quanta, 1 -- Singles, 2 -- Doubles, etc.
        @type maxexc: Integer
        """

        if maxexc > 4:
            raise Exception('At most quadruple excitations supported')

        states = []
        gs = [0] * self.nmodes
        states.append(gs)

        for i in range(self.nmodes):

            vec = [0] * self.nmodes
            vec[i] = 1
            states.append(vec)

            if maxexc > 1:
                vec = [0] * self.nmodes
                vec[i] = 2
                states.append(vec)

                for j in range(i+1, self.nmodes):
                    vec = [0] * self.nmodes
                    vec[i] = 1
                    vec[j] = 1
                    states.append(vec)

        if maxexc > 2:

            for i in range(self.nmodes):
                vec = [0]*self.nmodes
                vec[i] = 3
                states.append(vec)

                for j in range(i+1, self.nmodes):
                    vec = [0]*self.nmodes
                    vec[i] = 2
                    vec[j] = 1
                    states.append(vec)
                    vec = [0]*self.nmodes
                    vec[i] = 1
                    vec[j] = 2
                    states.append(vec)

                    for k in range(j+1, self.nmodes):
                        vec = [0]*self.nmodes
                        vec[i] = 1
                        vec[j] = 1
                        vec[k] = 1
                        states.append(vec)
        if maxexc > 3:

            for i in range(self.nmodes):
                vec = [0] * self.nmodes
                vec[i] = 4
                states.append(vec)

                for j in range(i+1, self.nmodes):
                    vec = [0]*self.nmodes
                    vec[i] = 3
                    vec[j] = 1
                    states.append(vec)
                    vec = [0]*self.nmodes
                    vec[i] = 1
                    vec[j] = 3
                    states.append(vec)
                    vec = [0]*self.nmodes
                    vec[i] = 2
                    vec[j] = 2
                    states.append(vec)

                    for k in range(j+1, self.nmodes):
                        vec = [0]*self.nmodes
                        vec[i] = 1
                        vec[j] = 1
                        vec[k] = 2
                        states.append(vec)
                        vec = [0]*self.nmodes
                        vec[i] = 1
                        vec[j] = 2
                        vec[k] = 1
                        states.append(vec)
                        vec = [0]*self.nmodes
                        vec[i] = 2
                        vec[j] = 1
                        vec[k] = 1
                        states.append(vec)

                        for l in range(k+1, self.nmodes):
                            vec = [0]*self.nmodes
                            vec[i] = 1
                            vec[j] = 1
                            vec[k] = 1
                            vec[l] = 1
                            states.append(vec)

        self.states = states

    def calculate_intensities(self, *dipolemoments):
        """
        Calculates VCI intensities using the dipole moment surfaces

        @param *dipolemoments: dipole moment surfaces, so far only 1- and 2-mode DMS supported
        @type dipolemoments: numpy.array
        """
        # TODO use dipole moment objects instead of pure arrays

        if len(dipolemoments) == 0:
            raise Exception('No dipole moments given')

        elif len(dipolemoments) == 1:
            raise Exception('Only one set of dipole moments given, go to VSCF_diag class')
        elif len(dipolemoments) > 2:
            print 'More than two sets of dipole moments given, only the two first will be used'

        if not self.solved:
            raise Exception('Solve the VCI first')

        self.dm1 = dipolemoments[0]
        self.dm2 = dipolemoments[1]

        # assuming that the first state is a ground state

        for i in range(1, len(self.states)):
            totaltm = 0.0
            for istate in range(len(self.states)):
                ci = self.vectors[istate, 0]  # initial state's coefficient

                for fstate in range(len(self.states)):
                    cf = self.vectors[fstate, i]  # final state's coefficient

                    tmptm = np.array([0.0, 0.0, 0.0])

                    for j in range(self.nmodes):
                        tmpd1 = np.array([0.0, 0.0, 0.0])
                        tmpovrlp = 1.0
                        jistate = self.states[istate][j]
                        jfstate = self.states[fstate][j]

                        for k in range(self.nmodes):
                            kistate = self.states[istate][k]
                            kfstate = self.states[fstate][k]

                            if k == j:
                                #  calculate <psi|u|psi>
                                tmpd1[0] += (self.dx[j] * self.wfns[j, jistate] * self.wfns[j, jfstate]
                                             * self.dm1[j, :, 0]).sum()
                                tmpd1[1] += (self.dx[j] * self.wfns[j, jistate] * self.wfns[j, jfstate]
                                             * self.dm1[j, :, 1]).sum()
                                tmpd1[2] += (self.dx[j] * self.wfns[j, jistate] * self.wfns[j, jfstate]
                                             * self.dm1[j, :, 2]).sum()

                            else:
                                if self.states[istate][k] == self.states[fstate][k]:
                                    tmpovrlp *= (self.dx[k] * self.wfns[k, kistate] * self.wfns[k, kfstate]).sum()
                                else:
                                    tmpovrlp = 0.0

                        tmptm += tmpd1 * tmpovrlp

                    for j in range(self.nmodes):
                        jistate = self.states[istate][j]
                        jfstate = self.states[fstate][j]
                        for k in range(j+1, self.nmodes):
                            tmpd2 = np.array([0.0, 0.0, 0.0])
                            kistate = self.states[istate][k]
                            kfstate = self.states[fstate][k]

                            for l in range(self.ngrid):
                                for m in range(self.ngrid):
                                    tmpd2[0] += self.dx[j] * self.dx[k] * self.dm2[j, k, l, m, 0] \
                                        * self.wfns[j, jistate, l] * self.wfns[j, jfstate, l] \
                                        * self.wfns[k, kistate, m] * self.wfns[k, kfstate, m]
                                    tmpd2[1] += self.dx[j] * self.dx[k] * self.dm2[j, k, l, m, 1] \
                                        * self.wfns[j, jistate, l] * self.wfns[j, jfstate, l] \
                                        * self.wfns[k, kistate, m] * self.wfns[k, kfstate, m]
                                    tmpd2[2] += self.dx[j] * self.dx[k] * self.dm2[j, k, l, m, 2] \
                                        * self.wfns[j, jistate, l] * self.wfns[j, jfstate, l] \
                                        * self.wfns[k, kistate, m] * self.wfns[k, kfstate, m]
                            tmpovrlp = 1.0

                            for n in range(self.nmodes):
                                if n != j and n != k:
                                    nistate = self.states[istate][n]
                                    nfstate = self.states[fstate][n]

                                    if nistate == nfstate:
                                        tmpovrlp *= (self.dx[n] * self.wfns[n, nistate] * self.wfns[n, nfstate]).sum()

                                    else:
                                        tmpovrlp = 0.0

                            tmptm += tmpd2 * tmpovrlp

                    totaltm += tmptm * ci * cf

            factor = 2.5048
            intens = (totaltm[0]**2 + totaltm[1]**2 + totaltm[2]**2) * factor * (self.energiesrcm[i]
                                                                                 - self.energiesrcm[0])
            print '%7.1f %7.1f' % (self.energiesrcm[i] - self.energiesrcm[0], intens)

    def _v1_integral(self, mode, lstate, rstate):  # calculate integral of type < mode(lstate) | V1 | mode(rstate) >

        s = (self.dx[mode] * self.wfns[mode, lstate] * self.wfns[mode, rstate] * self.v1[mode]).sum()

        return s

    def _v2_integral(self, mode1, mode2, lstate1, lstate2, rstate1, rstate2):
     # < mode1(lstate1) mode2(lstate2) | V2 | mode1(rstate1),mode2(rstate2)>

        s = 0.0

        for i in range(self.ngrid):
            si = self.dx[mode1] * self.wfns[mode1, lstate1, i] * self.wfns[mode1, rstate1, i]

            for j in range(self.ngrid):

                sj = self.dx[mode2] * self.wfns[mode2, lstate2, j] * self.wfns[mode2, rstate2, j]
                s += si * sj * self.v2[mode1, mode2, i, j]

        return s

    def _ovrlp_integral(self, mode, lstate, rstate):    # overlap integral < mode(lstates) | mode(rstate) >

        s = (self.dx[mode] * self.wfns[mode, lstate] * self.wfns[mode, rstate] * 1.0).sum()

        return s

    def _kinetic_integral(self, mode, lstate, rstate):  # kinetic energy integral < mode(lstate) | T | mode(rstate) >

        t = 0.0

        for i in range(self.ngrid):
            for j in range(self.ngrid):
                t += self.coefficients[mode, lstate, i] * self.coefficients[mode, rstate, j] * self.tij[mode, i, j]

        return t

    def _dgs_kinetic_integral(self, mode, i, j):  # integral between two DGs of the same modal centered at qi and qj

        a = self.a[mode]
        qi = self.grids[mode, i]
        qj = self.grids[mode, j]
        bij = (a + a)**0.5
        cij = (a*a)/(bij**2.0) * ((qi-qj)**2.0)
        ovrlp = self.sij[mode, i, j]

        return ovrlp * (a*a/(bij**2.0)) * (1.0-2.0*cij)

    def _dgs_ovrlp_integral(self, mode, i, j):  # overlap integral between two DGs of the same modal

        a = self.a[mode]
        qi = self.grids[mode, i]
        qj = self.grids[mode, j]
        aij = (4.0*a*a/(np.pi**2.0))**0.25
        bij = (a + a)**0.5
        cij = (a*a)/(bij**2.0)*((qi-qj)**2.0)
        return np.sqrt(np.pi)*(aij/bij)*np.exp(-cij)

    @staticmethod
    def _chi(q, a, qi):  # definition of a basis set function

        return ((2.0*a)/np.pi)**0.25*np.exp(-a*(q-qi)**2.0)

    def _calculate_coeff(self):  # calculates basis set coefficients, using grid and wave function values
        for i in range(self.nmodes):  # for each mode

            for j in range(self.ngrid):  # for each state

                #now calculate coefficients
                chi = np.zeros((self.ngrid, self.ngrid))
                for k in range(self.ngrid):
                    for l in range(self.ngrid):
                        chi[k, l] = self._chi(self.grids[i, l], self.a[i], self.grids[i, k])

                c = np.linalg.solve(chi, self.wfns[i, j])
                self.coefficients[i, j] = np.copy(c)

    def _calculate_kinetic_integrals(self):

        for i in range(self.nmodes):  # for each mode

            for j in range(self.ngrid):
                for k in range(self.ngrid):

                    self.tij[i, j, k] = self._dgs_kinetic_integral(i, j, k)

    def _calculate_ovrlp_integrals(self):

        for i in range(self.nmodes):  # for each mode

            for j in range(self.ngrid):
                for k in range(self.ngrid):

                    self.sij[i, j, k] = self._dgs_ovrlp_integral(i, j, k)