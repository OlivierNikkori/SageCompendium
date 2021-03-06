"""The symmetric superpolynomial module."""
from sage.structure.parent import Parent
from sage.structure.unique_representation import UniqueRepresentation
from sage.combinat.free_module import CombinatorialFreeModule
# from sage.categories.all import AlgebrasWithBasis
from sage.categories.all import Algebras
from sage.categories.realizations import Category_realization_of_parent
from sage.misc.bindable_class import BindableClass
from superpartition import Superpartitions, FermionicPartition
from superpartition import _Superpartitions
# from sage.combinat.partition import Partitions, Partition
from sage.misc.misc import uniq
import sympy
from sage.misc.misc_c import prod
from functools import reduce
import operator
from collections import Counter
from sage.functions.other import factorial
from sage.rings.rational_field import QQ
from sage.rings.infinity import Infinity
from sage.misc.cachefunc import cached_method
import six
# import itertools
from sage.symbolic.ring import SR
# from sage.symbolic.relation import solve
from sage.rings.all import Integer
from sage.arith.all import gcd, lcm
# from sage.symbolic.assumptions import assume
# from sage.misc.flatten import flatten
from sage.structure.sage_object import load, save
from sage.matrix.constructor import Matrix
from sage.interfaces.singular import singular
from sage.sets.set import Set
from sage.combinat.partition import Partition
from sage.combinat.sf.sf import SymmetricFunctions


def unique_permutations(seq):
    """Yield only unique permutations of seq in an efficient way."""
    """
    A python implementation of Knuth's "Algorithm L", also known from
    the std::next_permutation function of C++, and as the permutation
    algorithm of Narayana Pandita.
    """

    # Precalculate the indices we'll be iterating over for speed
    i_indices = range(len(seq) - 1, -1, -1)
    k_indices = i_indices[1:]

    # The algorithm specifies to start with a sorted version
    seq = sorted(seq)

    while True:
        yield seq

        # Working backwards from the last-but-one index,           k
        # we find the index of the first decrease in value.  0 0 1 0 1 1 1 0
        for k in k_indices:
            if seq[k] < seq[k + 1]:
                break
        else:
            # Introducing the slightly unknown python for-else syntax:
            # else is executed only if the break statement was never reached.
            # If this is the case, seq is weakly decreasing, and we're done.
            return

        # Get item from sequence only once, for speed
        k_val = seq[k]

        # Working backwards starting with the last item,           k     i
        # find the first one greater than the one at k       0 0 1 0 1 1 1 0
        for i in i_indices:
            if k_val < seq[i]:
                break

        # Swap them in the most efficient way
        (seq[k], seq[i]) = (seq[i], seq[k])  # k     i
        # 0 0 1 1 1 1 0 0

        # Reverse the part after but not                           k
        # including k, also efficiently.                     0 0 1 1 0 0 1 1
        seq[k + 1:] = seq[-1:k:-1]


def unique_perm_list_elements(lst):
    """Return the unique permutations of the elements of a list."""
    # unique_lst = list(set(lst))
    unique_lst = uniq(lst)
    # unique_int = [x for x in range(len(ulist))]
    my_map = {unique_lst[k]: k for k in range(len(unique_lst))}
    inv_map = {v: k for k, v in my_map.items()}

    int_lst = [my_map[n] for n in lst]
    perms = unique_permutations(int_lst)

    result = [[inv_map[n] for n in perm] for perm in perms]
    return result


class SymSuperfunctionsAlgebra(UniqueRepresentation, Parent):
    """The Class of Symmetric superfunctions."""

    def __init__(self, some_ring):
        """Initialize the algebra, cache and realizations."""
        self._base = some_ring
        my_cat = Algebras(some_ring)
        Parent.__init__(self,
                        category=my_cat.WithRealizations())
        self._Jack_m_cache = {}
        self._Macdo_m_cache = {}
        self._Schur_m_cache = {}
        self._SchurBar_m_cache = {}
        # attribute intialization
        # Construction of morphisms between bases
        # ...
        self._M = self.Monomial()
        self._P = self.Powersum()
        self._H = self.Homogeneous()
        self._E = self.Elementary()
        self._Schur = self.Schur()
        self._SchurBar = self.SchurBar()
        self._SchurStar = self.SchurStar()
        self._SchurBarStar = self.SchurBarStar()
        self._SFQQ = SymmetricFunctions(QQ)
        self._stdSchur = self._SFQQ.schur()
        self._stdP = self._SFQQ.powersum()
        self._stdH = self._SFQQ.homogeneous()
        self._stdE = self._SFQQ.elementary()
        category = self.Bases()

        # These implementation are a bit slow.
        # Optimization can be done here.
        self._p_to_m = self._P.module_morphism(
            self.morph_p_to_m, triangular='lower',
            codomain=self._M, category=category)
        self._m_to_p = ~(self._p_to_m)

        self._h_to_m = self._H.module_morphism(
            self.morph_h_to_m, codomain=self._M, category=category)
        self._h_to_p = self._H.module_morphism(
            self.morph_h_to_p, triangular='upper', invertible=True,
            codomain=self._P, category=category)
        self._p_to_h = ~(self._h_to_p)
        # The following comes from e_\Lambda = m_\Lambda.conjugate() + <
        # hence inverse_on_support which conjugate the super partitions.
        self._e_to_m = self._E.module_morphism(
            self.morph_e_to_m, codomain=self._M, category=category,
            triangular='upper', invertible=True,
            inverse_on_support=lambda spart: spart.conjugate())
        self._m_to_e = ~(self._e_to_m)

        # Coercion classical bases
        self._p_to_m.register_as_coercion()
        self._m_to_p.register_as_coercion()
        self._h_to_m.register_as_coercion()
        self._h_to_p.register_as_coercion()
        self._p_to_h.register_as_coercion()
        self._e_to_m.register_as_coercion()
        self._m_to_e.register_as_coercion()

        # Schur Basis
        # self._Schur_to_m = self._Schur.module_morphism(
        #     self.morph_Schur_to_m, triangular='upper', invertible=True,
        #     codomain=self._M, category=category)
        # self._m_to_Schur = ~(self._Schur_to_m)

        # self._SchurBar_to_m = self._SchurBar.module_morphism(
        #     self.morph_SchurBar_to_m, triangular='upper', invertible=True,
        #     codomain=self._M, category=category)
        # self._m_to_SchurBar = ~(self._SchurBar_to_m)

        self._SchurBar_to_SchurStar = self._SchurBar.module_morphism(
            self.morph_SchurBar_to_SchurStar,
            codomain=self._SchurStar, category=category)

        self._SchurStar_to_SchurBar = self._SchurStar.module_morphism(
            self.morph_SchurStar_to_SchurBar,
            codomain=self._SchurBar, category=category)

        self._Schur_to_SchurBarStar = self._Schur.module_morphism(
            self.morph_Schur_to_SchurBarStar,
            codomain=self._SchurBarStar, category=category)

        self._SchurBarStar_to_Schur = self._SchurBarStar.module_morphism(
            self.morph_SchurBarStar_to_Schur,
            codomain=self._Schur, category=category)

        # With Pieri
        self._p_to_Schur = self._P.module_morphism(
            self.morph_p_to_Schur,
            codomain=self._Schur, category=category)
        self._Schur_to_p = self._Schur.module_morphism(
            self.morph_Schur_to_p,
            codomain=self._P, category=category)

        self._h_to_SchurStar = self._H.module_morphism(
            self.morph_h_to_SchurStar,
            codomain=self._SchurStar, category=category)
        self._SchurStar_to_h = self._SchurStar.module_morphism(
            self.morph_SchurStar_to_h,
            codomain=self._H, category=category)

        self._e_to_SchurBar = self._E.module_morphism(
            self.morph_e_to_SchurBar,
            codomain=self._SchurBar, category=category)
        self._SchurBar_to_e = self._SchurBar.module_morphism(
            self.morph_SchurBar_to_e,
            codomain=self._E, category=category)

        self._p_to_SchurBarStar = self._P.module_morphism(
            self.morph_p_to_SchurBarStar,
            codomain=self._SchurBarStar, category=category)
        self._SchurBarStar_to_p = self._SchurBarStar.module_morphism(
            self.morph_SchurBarStar_to_p,
            codomain=self._P, category=category)
        # Coercion Schur
        # self._Schur_to_m.register_as_coercion()
        # self._m_to_Schur.register_as_coercion()
        # Now coercion from Pieri rules
        self._Schur_to_p.register_as_coercion()
        self._p_to_Schur.register_as_coercion()
        # self._SchurBar_to_m.register_as_coercion()
        # self._m_to_SchurBar.register_as_coercion()
        self._SchurStar_to_h.register_as_coercion()
        self._h_to_SchurStar.register_as_coercion()

        self._e_to_SchurBar.register_as_coercion()
        self._SchurBar_to_e.register_as_coercion()

        self._p_to_SchurBarStar.register_as_coercion()
        self._SchurBarStar_to_p.register_as_coercion()

        # self._SchurBar_to_SchurStar.register_as_coercion()
        # self._SchurStar_to_SchurBar.register_as_coercion()
        # self._SchurBarStar_to_Schur.register_as_coercion()
        # self._Schur_to_SchurBarStar.register_as_coercion()
        try:
            self._Schur_m_cache = load('./super_cache/Schur_m')
            self._SchurBar_m_cache = load('./super_cache/SchurBar_m')
        except:
            self._Schur_m_cache = dict({})
            self._SchurBar_m_cache = dict({})

        # One parameter bases
        if 'alpha' in some_ring.variable_names():
            # Galpha basis
            self._Galpha = self.Galpha()
            self._galpha_to_p = self._Galpha.module_morphism(
                self.morph_galpha_to_p, triangular='upper', invertible=True,
                codomain=self._P, category=category)
            self._p_to_galpha = ~(self._galpha_to_p)

            self._galpha_to_p.register_as_coercion()
            self._p_to_galpha.register_as_coercion()

            # Jack polynomials
            try:
                self._Jack_m_cache = load('./super_cache/Jack_m')
            except:
                self._Jack_m_cache = dict({})
            self._Jack = self.Jack()
            self._Jack_to_m = self._Jack.module_morphism(
                self.morph_Jack_to_m, triangular='upper', invertible=True,
                codomain=self._M, category=category)
            self._m_to_Jack = ~(self._Jack_to_m)
            self._Jack_to_m.register_as_coercion()
            self._m_to_Jack.register_as_coercion()

        # Handling the macdonald
        try:
            self._Macdo_m_cache = load('./super_cache/Macdo_m')
        except:
            self._Macdo_m_cache = dict({})
        var_names = some_ring.variable_names()
        if 'q' in var_names and 't' in var_names:
            self._Macdo = self.Macdonald()
            self._Macdo_to_m = self._Macdo.module_morphism(
                self.morph_Macdo_to_m, triangular='upper', invertible=True,
                codomain=self._M, category=category)
            self._m_to_Macdo = ~(self._Macdo_to_m)
            self._Macdo_to_m.register_as_coercion()
            self._m_to_Macdo.register_as_coercion()

            # Gqt
            self._Gqt = self.Gqt()
            self._gqt_to_p = self._Gqt.module_morphism(
                self.morph_gqt_to_p, triangular='upper', invertible=True,
                codomain=self._P, category=category)
            self._p_to_gqt = ~(self._gqt_to_p)

            self._gqt_to_p.register_as_coercion()
            self._p_to_gqt.register_as_coercion()

    _shorthands = ['m', 'h', 'p', 'e']

    @cached_method
    def morph_p_to_m(self, spart):
        """Take a spart and return the monomial expression of the powersum."""
        # The method uses the algorithm for the product of monomials
        Sparts = _Superpartitions
        if spart == _Superpartitions([[], []]):
            return self._M(1)
        ferm_list = [
            Sparts([[k], []]) for k in spart[0]]
        boso_list = [
            Sparts([[], [k]]) for k in spart[1]]
        all_sparts = ferm_list + boso_list
        # all_sparts.reverse()
        all_sparts = all_sparts
        all_monos = [self._M(a_spart) for a_spart in all_sparts]
        the_prod = reduce(operator.mul, all_monos, 1)
        return the_prod

    @cached_method
    def morph_h_to_m(self, spart):
        """Return the expansion of h(spart) on the monomial basis."""
        M = self._M
        if spart == _Superpartitions([[], []]):
            return M(1)
        ferm_list = [
            Superpartitions(k, 1) for k in spart[0]]
        boso_list = [
            Superpartitions(k, 0) for k in spart[1]]
        homos_tilde_n = [
            M.linear_combination(
                (M(spart), spart[0][0] + 1) for spart in sparts)
            for sparts in ferm_list]
        homos_n = [
            M.linear_combination(
                (M(spart), 1) for spart in sparts)
            for sparts in boso_list]
        homos = homos_tilde_n + homos_n
        the_prod = reduce(operator.mul, homos, 1)
        return the_prod

    @cached_method
    def morph_e_to_m(self, spart):
        """Return the expansion of e(spart) on the monomial basis."""
        M = self._M
        Sparts = Superpartitions()
        if spart == _Superpartitions([[], []]):
            return M(1)
        ferm_list = [
            Sparts([[0], [1 for k in range(part)]])
            for part in spart[0]]
        boso_list = [
            Sparts([[], [1 for k in range(part)]])
            for part in spart[1]]
        spart_list = ferm_list + boso_list
        mono_list = [M(a_spart) for a_spart in spart_list]
        the_prod = reduce(operator.mul, mono_list, 1)
        return the_prod

    @cached_method
    def morph_h_to_p(self, spart):
        """Convert h_Lambda to powersums."""
        """
        See Corollary 36 eq 3.61 of Classical Basis in superspace
        """
        P = self._P
        if spart == _Superpartitions([[], []]):
            return P(1)
        ferm_list = [list(Superpartitions(k, 1)) for k in spart[0]]
        boso_list = [list(Superpartitions(k, 0)) for k in spart[1]]
        spart_sets_list = ferm_list + boso_list
        # spart_sets_list.reverse()
        hns_plambda = [
            P.linear_combination(
                (P(spart), QQ(P.z_lambda(spart)**(-1))) for spart in sparts)
            for sparts in spart_sets_list]
        the_prod = reduce(operator.mul, hns_plambda, 1)
        return the_prod

    def morph_galpha_to_p(self, spart):
        """Convert galpha_Lambda to powersums."""
        # See compendium The one parameter of the ...
        P = self._P
        if spart == _Superpartitions([[], []]):
            return P(1)
        ferm_list = [list(Superpartitions(k, 1)) for k in spart[0]]
        boso_list = [list(Superpartitions(k, 0)) for k in spart[1]]
        spart_sets_list = ferm_list + boso_list
        BR = P.base_ring()
        alpha = BR.gens_dict()['alpha']
        gns_plambda = [
            P.linear_combination(
                (P(spart), BR(1/(P.z_lambda_alpha(spart, alpha))))
                for spart in sparts)
            for sparts in spart_sets_list]
        the_prod = reduce(operator.mul, gns_plambda, 1)
        return the_prod

    def morph_gqt_to_p(self, spart):
        """Convert galpha_Lambda to powersums."""
        # See compendium The one parameter of the ...
        # We should somehow make sure that the ring is OK.
        P = self._P
        BR = P.base_ring()
        if spart == _Superpartitions([[], []]):
            return P(1)
        ferm_list = [list(Superpartitions(k, 1)) for k in spart[0]]
        boso_list = [list(Superpartitions(k, 0)) for k in spart[1]]
        spart_sets_list = ferm_list + boso_list
        BR = P.base_ring()
        params = BR.gens()
        gns_plambda = [
            P.linear_combination(
                (P(spart), BR(1/(P.z_lambda_qt(spart, parameters=params))))
                for spart in sparts)
            for sparts in spart_sets_list]
        the_prod = reduce(operator.mul, gns_plambda, 1)
        ferm_deg = spart.fermionic_degree()
        sign = (-1)**(ferm_deg*(ferm_deg-1)/2)
        return sign*the_prod

    def morph_Jack_to_m(self, spart):
        """Return the monomial expansion of the Jack given spart."""
        # Here if the Jack is already cached, we return it
        # If not, we use the GramSchmidt procedure to obtain it
        if spart == _Superpartitions([[], []]):
            return self._M(1)
        sector = spart.sector()
        Jack_m_cache = self._Jack_m_cache
        M = self._M
        BR = M.base_ring()
        if sector in Jack_m_cache:
            the_dict = Jack_m_cache[sector][spart]
        else:
            print("The expansion of this Jack superpolynomial" +
                  " was not precomputed.")
            sect_dict = self._Jack._gram_sector(*sector)
            self._update_cache(sector, sect_dict, which_cache='Jack_m')
            the_dict = sect_dict[spart]
        spart_coeff = the_dict.items()
        mono_coeff = ((M(a_spart), BR(str(coeff)))
                      for a_spart, coeff in spart_coeff)
        out = M.linear_combination(mono_coeff)
        return out

    def morph_Macdo_to_m(self, spart):
        """Return the monomial expansion of the Jack given spart."""
        # Here if the Macdonald is already cached, we return it
        # If not, we use the GramSchmidt procedure to obtain it
        if spart == _Superpartitions([[], []]):
            return self._M(1)
        sector = spart.sector()
        Macdo_m_cache = self._Macdo_m_cache
        M = self._M
        BR = M.base_ring()
        if sector in Macdo_m_cache:
            the_dict = Macdo_m_cache[sector][spart]
        else:
            print("The expansion of this Macdonald superpolynomial" +
                  " was not precomputed.")
            sect_dict = self._Macdo._gram_sector(*sector)
            self._update_cache(sector, sect_dict, which_cache='Macdo_m')
            the_dict = sect_dict[spart]
        spart_coeff = the_dict.items()
        mono_coeff = ((M(a_spart), BR(coeff))
                      for a_spart, coeff in spart_coeff)
        out = M.linear_combination(mono_coeff)
        return out

    @staticmethod
    def _schur_qt_limit(coeff, lim):
        # First, if the coefficient is not a polynomial in either
        # q or t we don't have to do anything
        if coeff in QQ:
            return coeff

        # Now we must extract the ring from the coeff
        BR = coeff.parent()
        # This is a dictionnary with q, t and alpha
        parameters = BR.gens_dict()
        q = parameters['q']
        t = parameters['t']

        # Now we need to convert our coefficient to the symbolic ring
        coeff_SR = SR(coeff)
        # We also need a version of the parameters on the symbolic ring
        q_SR = SR(q)
        t_SR = SR(t)

        # We can now do the substitution since it is allowed on the
        # symbolic ring
        coeff_SR_q = coeff_SR.subs({q_SR: t_SR})

        # And here, one must understand that the limit is computed
        # by GAP and that the limit argument is sent by sage as a
        # string. So instead of writing t_SR = 1, we must write
        # t = 1 since t_SR is represented as the string 't'
        # in the equations
        coeff_lim = coeff_SR_q.limit(t=lim)

        return coeff_lim

    # Schur and p
    def morph_p_to_Schur(self, spart):
        """Return the Schur expansion of p[spart]."""
        S = self._Schur
        stdS = self._stdSchur
        stdP = self._stdP
        # The idea here is that p_\Lambda = p_\Lambda^a * p_\Lambda^s
        # and p_Lambda^s can be converted to standard Schur function
        # using standard Sage Libraries
        ptildes = list(spart[0])

        # The symmetric part is dealt with built in Schur functions
        psym = Partition(list(spart[1]))
        schur_dict = stdS(stdP(psym)).monomial_coefficients().items()
        # Convert to SuperSchur
        schur_dict = {_Superpartitions([[], list(part)]): coeff
                      for part, coeff in schur_dict}
        sSchur_expr = S.linear_from_dict(schur_dict)
        # Now we use Pieri for the fermionic part
        for row in ptildes:
            sSchur_expr = sSchur_expr._ptilde_rmul(row)

        return sSchur_expr

    def morph_h_to_SchurStar(self, spart):
        """Return the Schur expansion of p[spart]."""
        SStar = self._SchurStar
        stdS = self._stdSchur
        stdH = self._stdH
        # The idea here is that p_\Lambda = p_\Lambda^a * p_\Lambda^s
        # and p_Lambda^s can be converted to standard Schur function
        # using standard Sage Libraries
        htildes = list(spart[0])

        # The symmetric part is dealt with built-in Schur functions
        hsym = Partition(list(spart[1]))
        schur_dict = stdS(stdH(hsym)).monomial_coefficients().items()
        # Convert to SuperSchur
        schur_dict = {_Superpartitions([[], list(part)]): coeff
                      for part, coeff in schur_dict}
        sSchur_expr = SStar.linear_from_dict(schur_dict)
        # Now we use Pieri for the fermionic part
        for row in htildes:
            sSchur_expr = sSchur_expr._htilde_rmul(row)

        return sSchur_expr

    def morph_e_to_SchurBar(self, spart):
        """Return the SchurBar expansion of e[spart]."""
        Sbar = self._SchurBar
        stdS = self._stdSchur
        stdE = self._stdE
        # The idea here is that e_\Lambda = e_\Lambda^a * e_\Lambda^s
        # and p_Lambda^s can be converted to standard Schur function
        # using standard Sage Libraries
        etildes = list(spart[0])
        etildes.reverse()

        # The symmetric part is dealt with built-in Schur functions
        esym = Partition(list(spart[1]))
        schur_dict = stdS(stdE(esym)).monomial_coefficients().items()
        # Convert to SuperSchur
        schur_dict = {_Superpartitions([[], list(part)]): coeff
                      for part, coeff in schur_dict}
        sSchur_expr = Sbar.linear_from_dict(schur_dict)
        # Now we use Pieri for the fermionic part
        for row in etildes:
            sSchur_expr = sSchur_expr._etilde_rmul(row)

        return sSchur_expr

    def morph_Schur_to_p(self, spart):
        """Return the powesum expansion of a Schur polynomial."""
        p = self._P
        sector = spart.sector()
        sparts = list(Superpartitions(*sector))
        spart_index = sparts.index(spart)
        TM = self.TM_Schur_to_p(sector)
        sp_line = TM[spart_index]
        p_coeff = [
            (p(sparts[sp_index]), sp_line[sp_index])
            for sp_index in range(len(sparts))]
        return p.linear_combination(p_coeff)

    def morph_SchurStar_to_h(self, spart):
        """Return the powesum expansion of a Schur polynomial."""
        h = self._H
        sector = spart.sector()
        sparts = list(Superpartitions(*sector))
        spart_index = sparts.index(spart)
        TM = self.TM_SchurStar_to_h(sector)
        sp_line = TM[spart_index]
        h_coeff = [
            (h(sparts[sp_index]), sp_line[sp_index])
            for sp_index in range(len(sparts))]
        return h.linear_combination(h_coeff)

    def morph_SchurBar_to_e(self, spart):
        """Return the powesum expansion of a Schur polynomial."""
        e = self._E
        sector = spart.sector()
        sparts = list(Superpartitions(*sector))
        spart_index = sparts.index(spart)
        TM = self.TM_SchurBar_to_e(sector)
        sp_line = TM[spart_index]
        e_coeff = [
            (e(sparts[sp_index]), sp_line[sp_index])
            for sp_index in range(len(sparts))]
        return e.linear_combination(e_coeff)

    def morph_p_to_SchurBarStar(self, spart):
        """Return the Schur expansion of p[spart]."""
        S = self._SchurBarStar
        stdS = self._stdSchur
        stdP = self._stdP
        # The idea here is that p_\Lambda = p_\Lambda^a * p_\Lambda^s
        # and p_Lambda^s can be converted to standard Schur function
        # using standard Sage Libraries
        ptildes = list(spart[0])
        ptildes.reverse()

        # The symmetric part is dealt with built in Schur functions
        psym = Partition(list(spart[1]))
        schur_dict = stdS(stdP(psym)).monomial_coefficients().items()
        # Convert to SuperSchur
        schur_dict = {_Superpartitions([[], list(part)]): coeff
                      for part, coeff in schur_dict}
        sSchur_expr = S.linear_from_dict(schur_dict)
        # Now we use Pieri for the fermionic part
        for row in ptildes:
            sSchur_expr = sSchur_expr._ptilde_rmul(row)
        return sSchur_expr

    def morph_SchurBarStar_to_p(self, spart):
        """Return the powesum expansion of a Schur polynomial."""
        p = self._P
        sector = spart.sector()
        sparts = list(Superpartitions(*sector))
        spart_index = sparts.index(spart)
        TM = self.TM_SchurBarStar_to_p(sector)
        sp_line = TM[spart_index]
        e_coeff = [
            (p(sparts[sp_index]), sp_line[sp_index])
            for sp_index in range(len(sparts))]
        return p.linear_combination(e_coeff)

    # Schur to Schur
    def morph_SchurBar_to_SchurStar(self, spart):
        """Return the s* expansion of the sbar given a spart."""
        sstar_lambdaprime = self._SchurStar(spart.conjugate())
        omega_sstar = sstar_lambdaprime.omega()
        ferm_deg = spart.fermionic_degree()
        s_bar = (-1)**(ferm_deg*(ferm_deg-1)/2)*omega_sstar
        return s_bar

    def morph_SchurStar_to_SchurBar(self, spart):
        """Return the sbar expansion of the s* given a spart."""
        target = self._SchurBar
        s_lambdaprime = target(spart.conjugate())
        omega_s = s_lambdaprime.omega()
        ferm_deg = spart.fermionic_degree()
        out = (-1)**(ferm_deg*(ferm_deg-1)/2)*omega_s
        return out

    def morph_SchurBarStar_to_Schur(self, spart):
        """Return the monomial expansion of the dual Schur given a spart."""
        s_lambdaprime = self._Schur(spart.conjugate())
        omega_s = s_lambdaprime.omega()
        ferm_deg = spart.fermionic_degree()
        sbar_star = (-1)**(ferm_deg*(ferm_deg-1)/2)*omega_s
        return sbar_star

    # def morph_Schur_to_SchurBarStar(self, spart):
    #     """Return the dualr Schurbar of the Schur given a spart."""
    #     target = self._SchurBarStar
    #     s_lambdaprime = target(spart.conjugate())
    #     omega_s = s_lambdaprime.omega()
    #     ferm_deg = spart.fermionic_degree()
    #     out = (-1)**(ferm_deg*(ferm_deg-1)/2)*omega_s
    def morph_Schur_to_SchurBarStar(self, spart):
        """Return the dualr Schurbar of the Schur given a spart."""
        sbarstar = self._SchurStar
        sparts = list(Superpartitions(*spart.sector()))
        spart_index = sparts.index(spart)
        TM = self.TM_Schur_to_SchurBarStar(spart.sector())
        sp_line = TM[spart_index]
        s_coeff = [
            (sbarstar(sparts[sp_index]), sp_line[sp_index])
            for sp_index in range(len(sparts))
        ]
        return sbarstar.linear_combination(s_coeff)

    # Since the Sage morphism inversion only works on diagonal matrix
    # of transition, we build the matrices and invert them
    # This might be sub-optimal
    @cached_method
    def TM_p_to_Schur(self, sector):
        """Return the transition matrix p -> s."""
        sparts = Superpartitions(*sector)
        exprs = [self.morph_p_to_Schur(spart) for spart in sparts]
        TM = [
            [expr.coefficient(spart) for spart in sparts]
            for expr in exprs]
        TM = Matrix(QQ, TM)
        return TM

    @cached_method
    def TM_Schur_to_p(self, sector):
        """Return the transition matrix s -> p."""
        TMps = self.TM_p_to_Schur(sector)
        TM = TMps.inverse()
        return TM

    @cached_method
    def TM_p_to_SchurBarStar(self, sector):
        """Return the transition matrix p -> s."""
        sparts = Superpartitions(*sector)
        exprs = [self.morph_p_to_SchurBarStar(spart) for spart in sparts]
        TM = [
            [expr.coefficient(spart) for spart in sparts]
            for expr in exprs]
        TM = Matrix(QQ, TM)
        return TM

    @cached_method
    def TM_SchurBarStar_to_p(self, sector):
        """Return the transition matrix s -> p."""
        TMps = self.TM_p_to_SchurBarStar(sector)
        TM = TMps.inverse()
        return TM

    @cached_method
    def TM_h_to_SchurStar(self, sector):
        """Return the transition matrix p -> s*."""
        sparts = Superpartitions(*sector)
        exprs = [self.morph_h_to_SchurStar(spart) for spart in sparts]
        TM = [
            [expr.coefficient(spart) for spart in sparts]
            for expr in exprs]
        TM = Matrix(QQ, TM)
        return TM

    @cached_method
    def TM_SchurStar_to_h(self, sector):
        """Return the transition matrix s* -> p."""
        TMps = self.TM_h_to_SchurStar(sector)
        TM = TMps.inverse()
        return TM

    @cached_method
    def TM_e_to_SchurBar(self, sector):
        """Return the transition matrix p -> s*."""
        sparts = Superpartitions(*sector)
        exprs = [self.morph_e_to_SchurBar(spart) for spart in sparts]
        TM = [
            [expr.coefficient(spart) for spart in sparts]
            for expr in exprs]
        TM = Matrix(QQ, TM)
        return TM

    @cached_method
    def TM_SchurBar_to_e(self, sector):
        """Return the transition matrix s* -> p."""
        TMps = self.TM_e_to_SchurBar(sector)
        TM = TMps.inverse()
        return TM

    @cached_method
    def TM_SchurBarStar_to_Schur(self, sector):
        """Return the transition matrix sBarStar to Schur."""
        Sparts = Superpartitions(*sector)
        target = self._Schur
        origin = self._SchurBarStar
        expr = [target(origin(spart)) for spart in Sparts]
        TM = [
            [one_expr.coefficient(spart) for spart in Sparts]
            for one_expr in expr]
        TM = Matrix(QQ, TM)
        return TM

    @cached_method
    def TM_Schur_to_SchurBarStar(self, sector):
        """Return the transition matrix Schur to SchurBarStar."""
        TM = self.TM_SchurBarStar_to_Schur(sector)
        TM = TM.inverse()
        return TM

    @cached_method
    def TM_SchurBar_to_SchurStar(self, sector):
        """Return the transition matrix SchurStar to SchurBar."""
        Sparts = Superpartitions(*sector)
        target = self._SchurStar
        origin = self._SchurBar
        expr = [target(origin(spart)) for spart in Sparts]
        TM = [
            [one_expr.coefficient(spart) for spart in Sparts]
            for one_expr in expr]
        TM = Matrix(QQ, TM)
        return TM

    @cached_method
    def TM_SchurStar_to_SchurBar(self, sector):
        """Return the transition matrix SchurStar to SchurBar."""
        TM_sb_ss = self.TM_SchurBar_to_SchurStar(sector)
        TM = TM_sb_ss.inverse()
        return TM

    def morph_Schur_to_m(self, spart):
        """Return the monomial expansion of the Schur given spart."""
        # Obtain it from cache, if not cached obtain it as
        # the limit of the Macdonald
        if spart == _Superpartitions([[], []]):
            return self._M(1)
        sector = spart.sector()
        Schur_m_cache = self._Schur_m_cache
        M = self._M
        BR = M.base_ring()
        if sector in Schur_m_cache:
            the_dict = Schur_m_cache[sector][spart]
        else:
            print("The expansion of this Schur superpolynomial" +
                  " was not precomputed.")

            def schur_case(coeff):
                return SymSuperfunctionsAlgebra._schur_qt_limit(coeff, 0)

            # We define everything we need to obtain the Schur
            # from the monomial function
            _QQqt = QQ['q', 't'].fraction_field()
            _Symqt = SymSuperfunctionsAlgebra(_QQqt)
            _Macdo = _Symqt.Macdonald()
            _mono = _Symqt.Monomial()

            # To update the cache, we have to compute the whole
            # sector.
            sparts = Superpartitions(*sector)
            sect_dict = {
                a_spart:
                (_mono(_Macdo(a_spart))
                 ).map_coefficients(schur_case).monomial_coefficients()
                for a_spart in sparts
            }

            self._update_cache(sector, sect_dict, which_cache='Schur_m')
            the_dict = sect_dict[spart]
        spart_coeff = the_dict.items()
        mono_coeff = ((M(a_spart), BR(coeff))
                      for a_spart, coeff in spart_coeff)
        out = M.linear_combination(mono_coeff)
        return out

    def morph_SchurBar_to_m(self, spart):
        """Return the monomial expansion of the Schur given spart."""
        if spart == _Superpartitions([[], []]):
            return self._M(1)
        sector = spart.sector()
        Schur_m_cache = self._SchurBar_m_cache
        M = self._M
        BR = M.base_ring()
        if sector in Schur_m_cache:
            the_dict = Schur_m_cache[sector][spart]
        else:
            print("The expansion of this SchurBar superpolynomial" +
                  " was not precomputed.")

            def schurbar_case(coeff):
                return SymSuperfunctionsAlgebra._schur_qt_limit(
                    coeff, Infinity)

            # We define everything we need to obtain the Schur
            # from the monomial function
            _QQqt = QQ['q', 't'].fraction_field()
            _Symqt = SymSuperfunctionsAlgebra(_QQqt)
            _Macdo = _Symqt.Macdonald()
            _mono = _Symqt.Monomial()

            # To update the cache, we have to compute the whole
            # sector.
            sparts = Superpartitions(*sector)
            sect_dict = {
                a_spart:
                (_mono(_Macdo(a_spart))
                 ).map_coefficients(schurbar_case).monomial_coefficients()
                for a_spart in sparts
            }

            self._update_cache(sector, sect_dict, which_cache='SchurBar_m')
            the_dict = sect_dict[spart]
        spart_coeff = the_dict.items()
        # Here we must make sure that the coefficient is cast back
        # into the coeff ring. It will generate errors otherwise.
        mono_coeff = ((M(a_spart), BR(coeff))
                      for a_spart, coeff in spart_coeff)
        out = M.linear_combination(mono_coeff)
        return out

    def _update_cache(self, sector, cache_extension, which_cache=None):
        """Update and write to disk the cache of an object."""
        if which_cache == 'Jack_m':
            self._Jack_m_cache[sector] = cache_extension
            save(self._Jack_m_cache, filename='./super_cache/Jack_m')
        if which_cache == 'Macdo_m':
            self._Macdo_m_cache[sector] = cache_extension
            save(self._Macdo_m_cache, filename='./super_cache/Macdo_m')
        if which_cache == 'Schur_m':
            self._Schur_m_cache[sector] = cache_extension
            save(self._Schur_m_cache, filename='./super_cache/Schur_m')
        if which_cache == 'SchurBar_m':
            self._SchurBar_m_cache[sector] = cache_extension
            save(self._SchurBar_m_cache, filename='./super_cache/SchurBar_m')

    def a_realization(self):
        """Return the default realization."""
        return self._M

    def _repr_(self):
        out = "Symmetric superfunctions over " + str(self.base_ring())
        return out

    def _gram_schmidt(self, n, m, source, scalar,
                      leading_coeff=None, upper_triangular=True):
        """Apply Gram Schmidt procedure for sector given scalar product."""
        r"""
        This is copied from sage/combinat/sf, adapted for superpartitions.
        Apply Gram-Schmidt to ``source`` with respect to the scalar product
        ``scalar`` for all superpartitions of `n|M`. The scalar product is
        supposed
        to make the power-sum basis orthogonal. The Gram-Schmidt algorithm
        computes an orthogonal basis (with respect to the scalar product
        given by ``scalar``) of the `n`-th homogeneous component of the
        ring of symmetric functions such that the transition matrix from
        the basis ``source`` to this orthogonal basis is triangular.

        The implementation uses the powersum basis, so this function
        shouldn't be used unless the base ring is a `\QQ`-algebra
        (or ``self`` and ``source`` are both the powersum basis).

        INPUT:

        - ``n`` -- nonnegative integer which specifies the size of
          the partitions
        - ``m`` -- nonnegative integer which specifies the fermionic degree
        - ``source`` -- a basis of the ring of symmetric functions
        - ``scalar`` -- a function ``zee`` from partitions to the base ring
          which specifies the scalar product by `\langle p_{\lambda},
          p_{\lambda} \rangle = \mathrm{zee}(\lambda)`.
        - ``cache`` -- a cache function
        - ``leading_coeff`` -- (default: ``None``) specifies the leading
          coefficients for Gram-Schmidt
        - ``upper_triangular`` -- (defaults to ``True``) boolean, indicates
          whether the transition is upper triangular or not

        EXAMPLES::
            # TODO
        """
        BR = self.base_ring()
        one = BR.one()
        p = source.realization_of().Powersum()

        # Create a function which converts x and y to the power-sum basis
        # and applies the scalar product.
        pscalar = (lambda x, y:
                   p._apply_multi_module_morphism(
                       p(x), p(y), lambda a, b: scalar(a), orthogonal=True))

        if leading_coeff is None:
            leading_coeff = lambda x: one

        # We are going to be doing everything like we are in the
        # upper-triangular case. We list the partitions in "decreasing order"
        # and work from the beginning forward.
        # If we are in the lower-triangular case,
        # then we shouldn't reverse the list.
        l = list(Superpartitions(n, m))
        l = _Superpartitions.sort_by_dominance(l)
        if upper_triangular:
            l.reverse()

        # precomputed elements
        precomputed_elements = []
        cache = dict({})
        # Handle the initial case
        cache[l[0]] = {l[0]: leading_coeff(l[0])}
        precomputed_elements.append(leading_coeff(l[0])*source(l[0]))
        print("Computing...")
        total_loops = len(l)
        for i in range(1, len(l)):
            print(str(i)+" superpartitions computed out of " +
                  str(total_loops))
            start = leading_coeff(l[i])*source(l[i])
            sub = 0
            for j in range(i):
                sub += (
                    pscalar(start, precomputed_elements[j]) /
                    pscalar(precomputed_elements[j], precomputed_elements[j]) *
                    precomputed_elements[j]
                )
            res = start - sub
            res = res.map_coefficients(lambda x: BR(SR(x)))

            if hasattr(self, '_normalize_coefficients'):
                res = res.map_coefficients(self._normalize_coefficients)
            precomputed_elements.append(res)
            # Now, res == precomputed_elements[i]
            cache[l[i]] = {}
            for j in range(i+1):
                cache[l[i]][l[j]] = res.coefficient(l[j])
        return cache

    class Bases(Category_realization_of_parent):
        """General class for bases."""

        def super_categories(self):
            """Define the category of basis."""
            A = self.base()
            category = Algebras(A.base_ring())
            return [A.Realizations(),
                    category.Realizations().WithBasis()]

        class ParentMethods:
            """Code common to all bases of the algebra."""

            def __getitem__(self, args):
                """Allow abuse of notation."""
                """
                This method allows the abuse of notation where instead
                of writting
                > M = SymSuperfunctionsAlgebra(QQ)
                > SP = Superpartitions()
                > mono1 = M(SP([[3,2],[4,4]]))
                You can simply write
                > mono1 = M[[2,0], [4,1]]
                """
                return self.monomial(_Superpartitions(list(args)))

            def one(self):
                """Return the unit element."""
                Sp = Superpartitions()
                return self(Sp([[], []]))

            def is_multiplicative(self):
                """Tell wether or not a basis is multiplicative."""
                return isinstance(
                    self, SymSuperfunctionsAlgebra.MultiplicativeBasis)

            def _repr_(self):
                out = (str(self.realization_of()) + " in the " +
                       str(self._realization_name()) + " basis")
                return out

            def _apply_multi_module_morphism(self, x, y, f, orthogonal=False,
                                             parameters=None):
                """Apply function to pair of element of expr, ie scalarprod."""
                res = 0
                # BR = x.base_ring()
                if orthogonal:
                    coeffx = x.monomial_coefficients()
                    coeffy = y.monomial_coefficients()
                    spartx = set(coeffx.keys())
                    sparty = set(coeffy.keys())
                    sparts_set = spartx.intersection(sparty)
                    scals = {spart: f(spart, parameters)
                             for spart in sparts_set}
                    coeffs = [coeffx[spart]*coeffy[spart]*scals[spart]
                              for spart in sparts_set]
                    out = sum(coeffs)
                    return out
                else:
                    print('not orthognal')
                    for mono_x, coeff_x in six.iteritems(x._monomial_coefficients):
                        for mono_y, coeff_y in six.iteritems(y._monomial_coefficients):
                            res += coeff_x*coeff_y*f(mono_x, mono_y, parameters)
                    return res

            @staticmethod
            def z_lambda(spart, parameters=None):
                """Return the usual z_lambda function."""
                part_dict = Counter(list(spart[1]))
                ferm_degree = spart.fermionic_degree()
                sign = (-1)**(ferm_degree*(ferm_degree-1)/2)
                out = sign*prod([
                    k**part_dict[k] * factorial(part_dict[k])
                    for k in part_dict.keys()])
                return out

            @classmethod
            def z_lambda_alpha(cls, spart, alpha):
                """Alpha deformation of z_lambda."""
                return alpha**len(spart)*cls.z_lambda(spart)

            @classmethod
            def z_lambda_qt(cls, spart, parameters=None):
                """Return the value of z_Lambda(q,t)."""
                q, t = parameters
                term1 = q**(spart[0].degree())
                term2 = [(1-q**a_part)/(1-t**a_part) for a_part in spart[1]]
                term2 = prod(term2)
                return term1*term2*cls.z_lambda(spart)

            def from_polynomial(self, expr, superspace):
                """Obtain the basis representation of a superpolynomial."""
                mono = self.realization_of().Monomial()
                return self(mono._pol_to_mono(expr, superspace))

        class ElementMethods:
            """Code common to elements of all bases of the algebras."""

            def collect(self):
                """Simplify the coefficients."""
                spart_coeff = self.monomial_coefficients()
                parent = self.parent()
                BR = self.base_ring()
                return parent.linear_combination(
                    (parent(spart), BR(SR(spart_coeff[spart]).factor()))
                    for spart in spart_coeff
                )

            def subs_coeff(self, sub_dict):
                """Substitution for paremeters in the coefficients."""
                return self.map_coefficients(lambda x: x.subs(sub_dict))

            def omega(self):
                """Apply the omega involution to the expression."""
                # Might be a better idea to define this in the morphisms.

                # The way it works is
                # element -> powersum_expr
                # omega(powersum_expr)
                # omega(powersum_expr) -> element

                # One could overide this method in the element class
                # for faster implementation.
                P = self.parent().realization_of().Powersum()
                return self.parent(P(self).omega())

            def phi_t(self):
                """Apply the phi_t automoprhism."""
                P = self.parent().realization_of().Powersum()
                return self.parent(P(self).phi_t())

            def expand(self, superspace):
                """Expand the expression in terms of variables."""
                mono = self.parent().realization_of().Monomial()
                expr = mono(self)._mono_expand(superspace)
                return expr

            def omega_alpha(self, in_alpha=None):
                """Alpha deformation of the involution omega."""
                parent = self.parent()
                BR = parent.base_ring()
                P = parent.realization_of().Powersum()
                self_p = P(self)
                alpha = in_alpha
                if in_alpha is None:
                    alpha = BR.gens_dict()['alpha']
                one = BR.one()
                out = P._from_dict(
                    {
                        spart:
                        BR(SR(coeff*alpha**(
                            len(spart))*(-one)**(spart.bosonic_degree()
                                                 - len(spart[1]))))
                        for spart, coeff in self_p})
                return parent(out)

            def omega_qt(self, in_alpha=None):
                """Apply qt deformation of involution omega."""
                parent = self.parent()
                BR = parent.base_ring()
                P = parent.realization_of().Powersum()
                self_p = P(self)
                params = BR.gens_dict()
                q = params['q']
                t = params['t']

                one = BR.one()
                out = P._from_dict(
                    {
                        spart:
                        BR(SR(
                            coeff*q**(spart[0].degree())
                            * (-one)**(spart.bosonic_degree() - len(spart[1]))
                            * prod([(1-q**a_part)/(1-t**a_part)
                                   for a_part in spart[1]])
                        ))
                        for spart, coeff in self_p
                    }
                )
                return parent(out)

            def rho_qt(self):
                """The second automorphism in two parameters."""
                P = self.parent().realization_of().Powersum()
                parent = self.parent()
                self_in_p = P(self)
                rho_p = self_in_p.rho_qt()
                return parent(rho_p)

            @cached_method
            def scalar_product(self, other):
                """Apply scalar product for self * other."""
                P = self.parent().realization_of().Powersum()
                self_p = P(self)
                scal_prod = self_p.scalar_product(other)
                return scal_prod

            def scalar_alpha(self, other, in_alpha=None):
                """Apply alpha-deformed scalar product."""
                parent = self.parent()
                BR = parent.base_ring()
                P = parent.realization_of().Powersum()
                self_p = P(self)
                other_p = P(other)
                alpha = in_alpha
                if in_alpha is None:
                    params = BR.gens_dict()
                    alpha = params['alpha']
                    # if hasattr(parent, "alpha"):
                    #     alpha = parent.alpha
                    # else:
                    #     alpha = BR(QQ['alpha'].fraction_field().gen())
                _zee_alpha = P.z_lambda_alpha
                out = P._apply_multi_module_morphism(self_p, other_p,
                                                     _zee_alpha,
                                                     orthogonal=True,
                                                     parameters=alpha)
                # out = simplify(out)
                return out

            def scalar_qt(self, other):
                """Apply qt deformed scalar product."""
                parent = self.parent()
                BR = parent.base_ring()
                P = parent.realization_of().Powersum()
                self_p = P(self)
                other_p = P(other)
                if hasattr(parent, 'q') and hasattr(parent, 't'):
                    q = parent.q
                    t = parent.t
                else:
                    params = BR.gens_dict()
                    q = params['q']
                    t = params['t']

                _zee_qt = P.z_lambda_qt
                out = P._apply_multi_module_morphism(self_p, other_p,
                                                     _zee_qt,
                                                     orthogonal=True,
                                                     parameters=(q, t))
                # out = simplify(out)
                return out

            def zero(self):
                """Return 0."""
                return 0

            def one(self):
                """Return identity element."""
                Sp = Superpartitions()
                return self.parent(Sp([[], []]))

    class Basis(CombinatorialFreeModule, BindableClass):
        """Generic class for bases. Mainely for the constructor."""

        def __init__(self, A, **kwargs):
            """Initialize."""
            CombinatorialFreeModule.__init__(
                self, A.base_ring(), Superpartitions(),
                category=A.Bases(), bracket="", **kwargs)
            self._is_multiplicative = False

        def one(self):
            """Identity element."""
            return self(_Superpartitions([[], []]))

        def one_basis(self):
            """Identity element."""
            return _Superpartitions([[], []])

        def linear_from_dict(self, dic):
            """Return a linear combination of elements of basis given dict."""
            coef_elem = ((self(spart), coeff)
                         for spart, coeff in dic.iteritems())
            return self.linear_combination(coef_elem)

    class Monomial(Basis):
        """Class of the monomial basis."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='m')

        def one_basis(self):
            """Return the partition of element one."""
            return _Superpartitions([[], []])

        def _pol_to_mono(self, expr, superspace):
            """Convert a polynomial to an expression of monomials."""
            ss = superspace
            spart_coef = ss.var_to_monomials(expr)
            m = self
            BR = self.base_ring()
            monos = self.linear_combination((m(spart), BR(coeff))
                                            for spart, coeff
                                            in spart_coef.items())
            return monos

        @cached_method
        def product_on_basis(self, left, right):
            """Give the monomial expansion of the product of two monomials."""
            # The algorithm is based on
            # L. Alarie-Vezina, L. Lapointe and P. Mathieu.
            # N >= 2 symmetric superpolynomials.
            # The algorithm is given in Appendix B Monomial Product Algorithm
            # Algorithm step 1-3: add zeros so that the length are equal
            # And add letters in boxes and circles
            alt_a = left.switch_notation('a', len(right))
            alt_b = right.switch_notation('b', len(left))

            # Algorithm step 4: Permute entries of spartb and add it to 
            # sparta
            permutation_b = unique_perm_list_elements(alt_b)

            sums_a_b = [
                self.add_altnota_sparts(alt_a, x)
                for x in permutation_b
                if x != []
            ]
            # Algorithm step 5: we keep only one instance of each diagrams
            sums_a_b = set(sums_a_b)
            sums_a_b = [x for x in sums_a_b if x != ()]
            # Algorithm step 6: We find every distinct way of
            # permuting the rows.
            # Algorithm step 7: We find the associated sign
            coeffs = [self.give_prod_coeff(x) for x in sums_a_b]
            resulting_sparts = [
                Superpartitions.switch_back(x) for x in sums_a_b]
            monomials = [self(x) for x in resulting_sparts]
            poly = sum([x * y for x, y in zip(coeffs, monomials)])
            if poly == 0:
                poly = self(0)
            return poly

        @staticmethod
        def add_altnota_sparts(alt_sparta, alt_spartb):
            """Element wise adding of two alt notated sparts."""
            # This is meant only for the monomial product algorithm
            length = len(alt_sparta)
            out = []
            for k in range(length):
                parta = alt_sparta[k]
                partb = alt_spartb[k]
                value = parta[0] + partb[0]
                if parta[1] == 'box' and partb[1] == 'box':
                    the_type = 'box'
                elif parta[1] == 'circle' and partb[1] == 'circle':
                    the_type = 'NULL'
                    break
                else:
                    the_type = 'circle'
                ordering = tuple([parta[2], partb[2]])
                out += [tuple([value, the_type, ordering])]
            if the_type == 'NULL':
                out = []
            out.sort(reverse=True)
            fermions = [x[0:2] for x in out if x[1] == 'circle']
            fermions.sort()
            if fermions != uniq(fermions):
                out = []
            out = [tuple(x) for x in out if x[0:2] != (0, 'box')]
            return tuple(out)

        @staticmethod
        def give_prod_coeff(alt_spart):
            """Give the coefficient associated to spart in the mono_prod."""
            # We first compute the sign associated to this spart.
            # Following the algorithm of Alarie-Vezina et. al
            # N >= 2 symmetric superpolynomials
            #
            # We get the list of numbering of circles
            indices = [x[2] for x in alt_spart]
            indices = [item for sublist in indices for item in sublist]
            # We make sure they are indeed circles
            circ_indices = [x for x in indices if len(x) == 2]
            # We get the number of a symbols
            nb_a = sum(1 for x in circ_indices if x[0] == 'a')
            # We now procede to create a list of all the symbols
            # with [a, k] --> k
            # and [b, k] --> number_of_a + k
            # So that we have a permutation of (0,1,2,3, ...)
            # The parity of the permutation is the inversion number
            new_indices = []
            for index in circ_indices:
                if index[0] == 'a':
                    new_index = index[1]
                elif index[0] == 'b':
                    new_index = index[1] + nb_a
                new_indices.append(new_index)
            # The sign is given by the parity of the permutation
            the_sign = (-1)**FermionicPartition.inversion(new_indices)

            # Here we compute the multiplicity by
            # computing the number of ways there are to
            # distinguishably permute the lines on the diagram.

            # We first get one occurrence of each part
            value_type_spart = [x[:2] for x in alt_spart]
            skimmed_spart = uniq(value_type_spart)
            # We then get the adress of every part that are of the same
            # value and of the same type so that we can create a set with
            # all their complete value with indices.
            sets = []
            for a_term in skimmed_spart:
                their_address = [
                    i for i, x in enumerate(value_type_spart)
                    if x == a_term]
                sets += [[alt_spart[x] for x in their_address]]
            # The number we are looking for is the number of distinct
            # permutation of those sets hence the following piece of code
            coeff_set = [
                len(x) for x in
                [
                    list(sympy.utilities.iterables.multiset_permutations(y))
                    for y in sets]
            ]
            return the_sign * prod(coeff_set)

        class Element(CombinatorialFreeModule.Element):
            """Class for methods of elements of Monomial."""

            def _mono_expand(self, superspace):
                ss = superspace
                spart_coef = self.monomial_coefficients()
                sparts = spart_coef.keys()
                max_len = max([len(spart) for spart in sparts])
                if max_len > ss._N:
                    print('Warning, the number of variables of this superspace'
                          ' is less than the length of the longest'
                          ' superpartition, any monomial with len(lambda) > N'
                          ' will be set to 0.')
                var_monos = {
                    spart: singular(spart_coef[spart])*ss.monomial(spart)
                    for spart in spart_coef
                }
                expr = sum(var_monos.values())
                return expr

    m = Monomial

    class Schur(Basis):
        """Class of the type I super Schur."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='s')

        def spart_row_mult(self, spart, row, ferm=0):
            bos_deg = spart.bosonic_degree() + row
            ferm_deg = spart.fermionic_degree() + ferm
            sparts = Superpartitions(bos_deg, ferm_deg)

            valid_sparts = [self.is_RMI(Omega, spart, ferm)
                            for Omega in sparts]
            valid_sparts = [x for x in valid_sparts
                            if x is not None]
            out_dict = {omega: coeff for coeff, omega in valid_sparts}
            return out_dict

        @staticmethod
        def is_RMI(Om, other, ferm=True):
            Omega = Om
            Lambda = other

            # (dot)
            # Omega^*/Lambda* is r-strip
            OmCells = Set(Omega.cells())
            LamCells = Set(Lambda.cells())
            if not LamCells.issubset(OmCells):
                return None
            skew_star = OmCells.difference(LamCells)
            # We now check if two boxes are on top of each other
            # if so, it is not a strip
            j_coord = [x[1] for x in skew_star]
            if len(j_coord) != len(set(j_coord)):
                return None

            # (dot)
            # Omega/Lambda, the new circle is in the rightmost position
            OmAllCells = Set(Omega.all_cells())
            LamAllCells = Set(Lambda.all_cells())
            OmCircles = OmAllCells.difference(OmCells)
            LamCircles = LamAllCells.difference(LamCells)
            valid_OmCircles = list(OmCircles)
            if ferm:
                skew_circ_star = OmAllCells.difference(LamAllCells)
                rightmost_elem = max(skew_circ_star, key=lambda x: x[1])
                if rightmost_elem not in OmCircles:
                    return None
                j_coord = [x[1] for x in skew_circ_star]
                if len(j_coord) != len(set(j_coord)):
                    return None
                else:
                    valid_OmCircles.remove(rightmost_elem)
            # Now We make sure that we can map every circle of Lambda
            # to a circle of Omega according to the rules.
            for circ in LamCircles:
                # If the circle is in its original position
                # all is fine
                if circ in valid_OmCircles:
                    valid_OmCircles.remove(circ)
                else:
                    Om_i_coords = [x[0] for x in valid_OmCircles]
                    # (i) If the circle is in the first row, it can be moved
                    # horizontally without restrictions
                    if circ[0] == 1 and 1 in Om_i_coords:
                        the_circ = valid_OmCircles[Om_i_coords.index(1)]
                        if the_circ < circ:
                            return None
                        else:
                            valid_OmCircles.remove(the_circ)
                    # (ii) If the circle is in its original row
                    elif circ[0] in Om_i_coords:
                        # it can be moved to the right as long as there is
                        # a box over the circle in the original diagram
                        if circ[1] > Lambda.star()[circ[0]-2]:
                            return None
                        else:
                            the_circ = valid_OmCircles[
                                Om_i_coords.index(circ[0])]
                            valid_OmCircles.remove(the_circ)
                    elif (circ[0] + 1, circ[1]) in valid_OmCircles:
                        valid_OmCircles.remove((circ[0]+1, circ[1]))
                    else:
                        return None
            if ferm:
                sign = [1 for x in OmCircles
                        if rightmost_elem[1] > x[1]]
                sign = (-1)**sum(sign)
            else:
                sign = 1
            return [sign, Omega]

            @staticmethod
            def spart_column_mult(spart, r):
                pass

        class Element(CombinatorialFreeModule.Element):
            """Schur element class."""

            def _ptilde_rmul(self, n):
                """Right multiply a schur expression by p[[n],[]]."""
                S = self.parent()
                spart_coeff = self.monomial_coefficients()
                new_exprs = [
                    coeff *
                    S.linear_from_dict(
                        S.spart_row_mult(spart, n, ferm=1))
                    for spart, coeff in spart_coeff.iteritems()]
                return sum(new_exprs)

            def _h_rmul(self, n):
                """Right multiply a schur expression by h[[],[n]]."""
                S = self.parent()
                spart_coeff = self.monomial_coefficients()
                new_exprs = [
                    coeff *
                    S.linear_from_dict(
                        S.spart_row_mult(spart, n, ferm=0))
                    for spart, coeff in spart_coeff.iteritems()]
                return sum(new_exprs)

    class SchurBar(Basis):
        """Class of the type II super Schur."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='sbar')

        def spart_col_mult(self, spart, row, ferm=0):
            sstar = self.realization_of().SchurStar()
            sstar_dict = sstar.spart_row_mult(spart.conjugate(), row, ferm)
            sbar_dict = {omega.conjugate(): coeff
                         for omega, coeff in sstar_dict.iteritems()}
            return sbar_dict

        class Element(CombinatorialFreeModule.Element):
            """SchurBar element class."""

            def _etilde_rmul(self, n):
                """Rmul a SchuBar expr by e[[n],[]]."""
                sbar = self.parent()
                spart_coeff = self.monomial_coefficients()
                new_exprs = [
                    coeff *
                    sbar.linear_from_dict(
                        sbar.spart_col_mult(spart, n, ferm=1))
                    for spart, coeff in spart_coeff.iteritems()]
                return sum(new_exprs)

    class SchurStar(Basis):
        """Class of the type I dual super Schur."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='sStar')

        def spart_row_mult(self, spart, row, ferm=0):
            bos_deg = spart.bosonic_degree() + row
            ferm_deg = spart.fermionic_degree() + ferm
            sparts = Superpartitions(bos_deg, ferm_deg)

            valid_sparts = [self.is_RMII(Omega, spart, ferm)
                            for Omega in sparts]
            valid_sparts = [x for x in valid_sparts
                            if x is not None]
            out_dict = {omega: coeff for coeff, omega in valid_sparts}
            return out_dict

        @staticmethod
        def is_RMII(Omega, Lambda, ferm=True):
            # First r-strip condition:
            OmCells = Set(Omega.cells())
            LamCells = Set(Lambda.cells())
            if not LamCells.issubset(OmCells):
                return None
            skew_star = OmCells.difference(LamCells)
            # We now check if two boxes are on top of each other
            # if so, it is not a strip
            j_coord = [x[1] for x in skew_star]
            j_coord.sort()
            if len(j_coord) != len(set(j_coord)):
                return None

            # (dot) i-th circle
            OmAllCells = Set(Omega.all_cells())
            LamAllCells = Set(Lambda.all_cells())
            OmCircles = OmAllCells.difference(OmCells)
            LamCircles = list(LamAllCells.difference(LamCells))
            LamCircles.sort(reverse=True)
            valid_OmCircles = list(OmCircles)
            OmCircles_i = [x[0] for x in valid_OmCircles]
            i_coord = [x[0] for x in skew_star]
            # There must be a one to one maping between
            # circles of Lambda to circles of Omega
            for circ in LamCircles:
                ith = circ[0]
                if ith not in i_coord and ith in OmCircles_i:
                    valid_OmCircles.remove(circ)
                elif ith in i_coord and ith+1 in OmCircles_i:
                    the_circ = [x for x in valid_OmCircles
                                if x[0] == ith+1][0]
                    valid_OmCircles.remove(the_circ)
                else:
                    return None
                OmCircles_i = [x[0] for x in valid_OmCircles]
            # There should be one OmCircle left if we added a fermionic
            # column
            if ferm and len(valid_OmCircles) == 1:
                added_circ = valid_OmCircles[0]
                # No new box can lie over the added circle
                if added_circ[1] in j_coord:
                    return None
                # There must be a new box in every column on the left
                # of the new circle
                if j_coord[:added_circ[1]-1] != range(1, added_circ[1]):
                    return None
                # we count the number of cirle below
                circ_below = [1 for x in OmCircles
                              if x[0] > added_circ[0]]
                sign = (-1)**sum(circ_below)
            else:
                sign = 1

            return [sign, Omega]

        class Element(CombinatorialFreeModule.Element):
            """SchurStar element class."""

            def _htilde_rmul(self, n):
                """Right multiply a SchurStar expression by h[[n],[]]."""
                SStar = self.parent()
                spart_coeff = self.monomial_coefficients()
                new_exprs = [
                    coeff *
                    SStar.linear_from_dict(
                        SStar.spart_row_mult(spart, n, ferm=1))
                    for spart, coeff in spart_coeff.iteritems()]
                return sum(new_exprs)

    class SchurBarStar(Basis):
        """Class of the type II dual super Schur."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='sbarStar')

        def spart_col_mult(self, spart, row, ferm=0):
            s = self.realization_of().Schur()
            s_dict = s.spart_row_mult(spart.conjugate(), row, ferm)
            sbarstar_dict = {omega.conjugate(): coeff
                             for omega, coeff in s_dict.iteritems()}
            return sbarstar_dict

        class Element(CombinatorialFreeModule.Element):
            """SchurBarStar element class."""

            def _ptilde_rmul(self, n):
                """Rmul a SchuBar expr by p[[n],[]]."""
                sbar = self.parent()
                spart_coeff = self.monomial_coefficients()
                new_exprs = [
                    coeff *
                    sbar.linear_from_dict(
                        sbar.spart_col_mult(spart, n, ferm=1))
                    for spart, coeff in spart_coeff.iteritems()]
                return sum(new_exprs)

    class MultiplicativeBasis(Basis):
        """Generic class for multiplicative bases."""

        def __init__(self, A, **kwargs):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, **kwargs)

        def product_on_basis(self, left, right):
            """Return the product of left and right."""
            the_sign, the_spart = left + right
            return the_sign * self(the_spart)

    class Powersum(MultiplicativeBasis):
        """Class for the powersum basis."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.MultiplicativeBasis.__init__(
                self, A, prefix='p')

        def _rho_qt_spart(self, spart):
            BR = self.base_ring()
            P = self
            q, t, _ = BR.gens()
            bosonic = P(_Superpartitions([[], list(spart[1])]))
            bosonic = bosonic.omega_qt()

            ferm_list = list(spart[0])

            def rho_ptilde(k, q, t, P):
                sparts = Superpartitions(k, 1)
                BR = P.base_ring()
                p_list = [(-1)**(spart.bosonic_degree() - len(spart[1])) *
                          (1/BR(P.z_lambda(spart))) *
                          prod((1-q**(part_i)) for part_i in spart[1]) *
                          P(spart)
                          for spart in sparts]
                return sum(p_list)
            fermionics = [rho_ptilde(k, q, t, P) for k in ferm_list]
            fermionic = reduce(operator.mul, fermionics, 1)
            return fermionic*bosonic

        class Element(CombinatorialFreeModule.Element):
            """Class for methods of elements of basis."""

            def omega(self):
                """Return the omega automorphism on the powersum basis."""
                # map_item(f), f must be a function that returns (index, coeff)
                def f(*args):
                    spart, coeff = args
                    return (spart, (-1)**(spart.bosonic_degree() +
                                          len(spart[1]))*coeff)
                return self.map_item(f)

            def scalar_product(self, other):
                """Scalar product over powersum basis."""
                P = self.parent()
                other_p = P(other)
                return P._apply_multi_module_morphism(self, other_p,
                                                      P.z_lambda,
                                                      orthogonal=True)

            def phi_t(self):
                """Apply the phi_t automorphism on powersums."""
                def phi_spart(spart, t):
                    coeff = [(1-t**r)**(-1) for r in spart[1]]
                    coeff = reduce(operator.mul, coeff, 1)
                    return coeff

                t = self.base_ring().gens_dict()['t']
                P = self.parent()

                spart_coeff = self.monomial_coefficients()
                spart_phicoeff = {
                    spart: spart_coeff[spart]*phi_spart(spart, t)
                    for spart in spart_coeff}
                return P.linear_combination(
                    ((P(spart), spart_phicoeff[spart])
                     for spart in spart_phicoeff))

            def rho_qt(self):
                """Return the rho_qt automorphism of self."""
                spart_coeff = self.monomial_coefficients().items()
                P = self.parent()
                rho_spart = P._rho_qt_spart
                lin_list = [coeff*rho_spart(spart)
                            for spart, coeff in spart_coeff]
                return sum(lin_list)

    p = Powersum

    class Elementary(MultiplicativeBasis):
        """Elementary basis."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.MultiplicativeBasis.__init__(
                self, A, prefix='e')

    e = Elementary

    class Homogeneous(MultiplicativeBasis):
        """Homogeneous basis."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.MultiplicativeBasis.__init__(
                self, A, prefix='h')

    h = Homogeneous

    class Galpha(MultiplicativeBasis):
        """Alpha deformation of homogeneous basis."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.MultiplicativeBasis.__init__(
                self, A, prefix='galpha')

    galpha = Galpha

    class Gqt(MultiplicativeBasis):
        """q,t-deformation of the homogeneous basis."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.MultiplicativeBasis.__init__(
                self, A, prefix='gqt')

    gqt = Gqt

    class Jack(Basis):
        """ Class for the Jack superpolynomials. """

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='Palpha')

        @staticmethod
        def calc_norm(spart, param='alpha'):
            """Return the norm calculated with formula."""
            if param == 'alpha':
                QQa = QQ['alpha'].fraction_field()
                alpha = QQa.gen()
            else:
                alpha = param
            ferm_degree = spart.fermionic_degree()
            alpha_factor = alpha**ferm_degree
            coords = spart.bosonic_cells()
            hooks = [
                (
                    spart.upper_hook_length(i, j, alpha) /
                    spart.lower_hook_length(i, j, alpha)
                )
                for i, j in coords
            ]
            norm = alpha_factor*reduce(operator.mul, hooks, 1)
            return norm

        def _gram_sector(self, n, m):
            """Apply Gram Schmidt to solve for the sector."""
            Sym = self.realization_of()
            mono = Sym.Monomial()
            alpha = self.base_ring().gens_dict()['alpha']
            cache = Sym._gram_schmidt(n, m, mono,
                                      lambda sp: part_scalar_jack(sp, sp,
                                                                  alpha),
                                      upper_triangular=True)
            return cache

        class Element(CombinatorialFreeModule.Element):
            """Jack element class."""

            def evaluation(self, NbVars):
                BR = self.base_ring()
                alpha = BR.gens_dict()['alpha']

                def _eval_spart(spart, N, alpha):
                    BLambda = spart.bosonic_cells()
                    hooks = [spart.lower_hook_length(i, j, alpha)
                             for i, j in BLambda]
                    vlambda = reduce(operator.mul, hooks, 1)

                    ferm_deg = spart.fermionic_degree()
                    delta_m = _Superpartitions([[], range(ferm_deg, 0, -1)])
                    delta_m_coords = delta_m.cells()

                    spart_CS = _Superpartitions([[],
                                                 list(spart.circle_star())])
                    coords = spart_CS.cells()
                    deltaLambda = [coord
                                   for coord in coords
                                   if coord not in delta_m_coords]
                    second_prod = [N - (i - 1) + alpha*(j - 1)
                                   for (i, j) in deltaLambda]
                    second_prod = reduce(operator.mul, second_prod, 1)
                    return second_prod/vlambda

                spart_coef = self.monomial_coefficients().items()
                terms = [coef*_eval_spart(spart, NbVars, alpha)
                         for spart, coef in spart_coef]
                return reduce(operator.add, terms)

    class Macdonald(Basis):
        """Class for the Macdonald superpolynomials."""

        def __init__(self, A):
            """Initialize the combinatorial module."""
            SymSuperfunctionsAlgebra.Basis.__init__(
                self, A, prefix='Pqt')

        def _gram_sector(self, n, m):
            """Apply GramSchmidt to solve for whole sector."""
            Sym = self.realization_of()
            mono = Sym.Monomial()
            params = self.base_ring().gens_dict()
            q, t = [params['q'], params['t']]
            cache = Sym._gram_schmidt(n, m, mono,
                                      lambda sp: mono.z_lambda_qt(sp, (q, t)),
                                      upper_triangular=True)
            return cache

        @staticmethod
        def calc_norm(spart, param='qt'):
            """Return the norm of sMacdonald associated to spart."""
            if isinstance(spart, list):
                spart = _Superpartitions(spart)
            if param == 'qt':
                QQqt = QQ['q', 't'].fraction_field()
                q, t = QQqt.gens()
            else:
                raise ValueError("Innapropriate coefficient ring.")
            coords = spart.bosonic_cells()
            ferm_degree = spart.fermionic_degree()
            lambda_a_degree = sum(spart[0])
            prefactor = (
                            (-1)**(ferm_degree*(ferm_degree-1)/2) *
                            (q**lambda_a_degree)
                        )
            terms = [
                (
                    (1-(q**(spart.star().arm_length(i, j)+1) *
                     t**(spart.circle_star().leg_length(i, j)))) /
                    (1-(q**(spart.circle_star().arm_length(i, j)) *
                     t**(spart.star().leg_length(i, j)+1)))
                )
                for i, j in coords
            ]
            norm = prefactor*reduce(operator.mul, terms, 1)
            return norm

        class Element(CombinatorialFreeModule.Element):
            """Class for methods on elements of Macdonald basis."""

            def wqt_Lambda(self, q, t, spart):
                """Return prod_B(Lambda) (1-q^(a_star(s)+1)*t^l_cstar(s))."""
                bosonic_cells = spart.bosonic_cells()
                star = spart.star()
                cstar = spart.circle_star()
                terms = [(1 -
                          q**(star.arm_length(i, j) +
                              1)*t**(cstar.leg_length(i, j)))
                         for i, j in bosonic_cells]
                return reduce(operator.mul, terms, 1)

            def hlo_Lambda(self, q, t, spart):
                """Return the qt lower hook associeted to spart."""
                bosonic_cells = spart.bosonic_cells()
                star = spart.star()
                cstar = spart.circle_star()
                terms = [(1 -
                          q**(cstar.arm_length(i, j)
                              )*t**(star.leg_length(i, j) + 1))
                         for i, j in bosonic_cells]
                return reduce(operator.mul, terms, 1)

            def specialize(self, N, P_norm=True):
                """Specialize the sMacdo."""
                BR = self.base_ring()
                params = BR.gens_dict()
                q = params['q']
                t = params['t']
                wqt = self.hlo_Lambda
                # This pretty much goes as is illustrated in the compendium

                def _eval_spart(spart, wqt, N, q, t):
                    ferm_deg = spart.fermionic_degree()
                    stair = _Superpartitions.stair(ferm_deg - 1)
                    stairplus = _Superpartitions.stair(ferm_deg)

                    zetaL = spart.zeta()
                    bSL = spart.circle_star().b() - stairplus.b()
                    exp_denom = (
                        (ferm_deg - 1)*(spart[0].degree() - stair.degree()) -
                        (spart[0].b() - stair.b()))
                    normp = wqt(q, t, spart)

                    term1 = (t**(zetaL) * t**(bSL)) / (q**(exp_denom))
                    term1 = (1/normp)*term1

                    stair = stairplus
                    stair = _Superpartitions([[], list(stair)])
                    stair_cells = stair.cells()
                    csCells = spart.circle_star().cells()
                    SLambda_cells = [s
                                     for s in csCells
                                     if s not in stair_cells]

                    terms2 = [1 - q**(j-1)*t**(N-(i-1))
                              for i, j in SLambda_cells]
                    term2 = reduce(operator.mul, terms2, 1)

                    return term1 * term2

                spart_coef = self.monomial_coefficients().items()
                terms = [coef*_eval_spart(spart, wqt, N, q, t)
                         for spart, coef in spart_coef]
                return reduce(operator.add, terms)


# Deprecating
def normalize_coefficients(self, c):
    """Normalize. Helper functions, deprecating."""
    r"""
    If our coefficient ring is the field of fractions over a univariate
    polynomial ring over the rationals, then we should clear both the
    numerator and denominator of the denominators of their
    coefficients.

    INPUT:

    - ``self`` -- a Jack basis of the symmetric functions
    - ``c`` -- a coefficient in the base ring of ``self``

    OUTPUT:

    - divide numerator and denominator by the greatest common divisor

    EXAMPLES::

        sage: JP = SymmetricFunctions(FractionField(QQ['t'])).jack().P()
        sage: t = JP.base_ring().gen()
        sage: a = 2/(1/2*t+1/2)
        sage: JP._normalize_coefficients(a)
        4/(t + 1)
        sage: a = 1/(1/3+1/6*t)
        sage: JP._normalize_coefficients(a)
        6/(t + 2)
        sage: a = 24/(4*t^2 + 12*t + 8)
        sage: JP._normalize_coefficients(a)
        6/(t^2 + 3*t + 2)
    """
    if True:
        denom = c.denominator()
        numer = c.numerator()

        # Clear the denominators
        a = lcm([i.denominator() for i in denom.coefficients()])
        b = lcm([i.denominator() for i in numer.coefficients()])
        l = Integer(a).lcm(Integer(b))
        denom *= l
        numer *= l

        # Divide through by the gcd of the numerators
        a = gcd([i.numerator() for i in denom.coefficients()])
        b = gcd([i.numerator() for i in numer.coefficients()])
        l = Integer(a).gcd(Integer(b))

        denom = denom // l
        numer = numer // l

        return c.parent()(numer, denom)
    else:
        return c


def part_scalar_jack(spart1, spart2, alpha):
    """Alpha scalar product for 2 sparts."""
    if spart1 != spart2:
        return 0
    else:
        out = alpha**len(spart1)*spart1.z_lambda()
        return out

