import logging

import numpy as np
from scipy.constants import h, k, N_A, pi

from monty.json import MSONable

from pymatgen.core.units import amu_to_kg
from pymatgen.util.num import product


__author__ = "Evan Spotte-Smith"
__version__ = "0.1"
__maintainer__ = "Evan Spotte-Smith"
__email__ = "espottesmith@gmail.com"
__status__ = "Alpha"
__date__ = "September 2019"

logger = logging.getLogger(__name__)


class ReactionRateCalculator(MSONable):

    """
    An object which represents a chemical reaction (in terms of reactants, transition state,
    and products) and which can, from the energetics of those individual molecules, predict the
    rate constant, rate law, and thus the chemical kinetics of the reaction.

    NOTE: It is assumed that only one transition state is present.

    Args:
        reactants (list): list of MoleculeEntry objects
        products (list): list of MoleculeEntry objects
        transition_state (MoleculeEntry): MoleculeEntry representing the transition state between
            the reactants and the products

    Returns:
        None
    """

    def __init__(self, reactants, products, transition_state):
        """

        """

        self.reactants = reactants
        self.products = products
        self.transition_state = transition_state

        # Assume rate law is first-order in terms of each reactant/product
        rate_law = {"reactants": {ii: 1 for ii in range(len(self.reactants))},
                    "products": {jj: 1 for jj in range(len(self.products))}}

        self.rate_law = rate_law

    @property
    def net_energy(self):
        """
        Calculate net reaction energy (in eV).
        """
        rct_energies = [r.energy for r in self.reactants]
        pro_energies = [p.energy for p in self.products]

        return (sum(pro_energies) - sum(rct_energies)) * 27.2116

    @property
    def net_enthalpy(self):
        """
        Calculate net reaction enthalpy (in eV).
        """
        rct_enthalpies = [r.enthalpy for r in self.reactants]
        pro_enthalpies = [p.enthalpy for p in self.products]

        return (sum(pro_enthalpies) - sum(rct_enthalpies)) * 0.0433641

    @property
    def net_entropy(self):
        """
        Calculate net reaction entropy (in eV/K).
        """
        rct_entropies = [r.entropy for r in self.reactants]
        pro_entropies = [p.entropy for p in self.products]

        return (sum(pro_entropies) - sum(rct_entropies)) * 0.0000433641

    def calculate_net_gibbs(self, temperature=298.0):
        """
        Calculate net reaction Gibbs free energy at a given temperature.

        ΔG = ΔH - T ΔS

        Args:
            temperature (float): absolute temperature in Kelvin

        Returns:
            float: net Gibbs free energy (in eV)
        """

        rct_gibbs = [r.free_energy(temp=temperature) for r in self.reactants]
        pro_gibbs = [p.free_energy(temp=temperature) for p in self.products]

        return sum(pro_gibbs) - sum(rct_gibbs)

    def calculate_net_thermo(self, temperature=298.0):
        """
        Calculate net energy, enthalpy, and entropy for the reaction.

        Args:
            temperature (float): absolute temperature in Kelvin (default 300.0K)

        Returns:
            net_thermo: dict with relevant net thermodynamic variables
        """

        net_thermo = {"energy": self.net_energy,
                      "enthalpy": self.net_enthalpy,
                      "entropy": self.net_entropy,
                      "gibbs": self.calculate_net_gibbs(temperature)}

        return net_thermo

    def calculate_act_energy(self, reverse=False):
        """
        Calculate energy of activation.

        Args:
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            float: energy of activation (in eV)

        """

        trans_energy = self.transition_state.energy

        if reverse:
            pro_energies = [p.energy for p in self.products]
            return (trans_energy - sum(pro_energies)) * 27.2116
        else:
            rct_energies = [r.energy for r in self.reactants]
            return (trans_energy - sum(rct_energies)) * 27.2116

    def calculate_act_enthalpy(self, reverse=False):
        """
        Calculate enthalpy of activation.

        Args:
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            float: enthalpy of activation (in eV)

        """

        trans_enthalpy = self.transition_state.enthalpy

        if reverse:
            pro_enthalpies = [p.enthalpy for p in self.products]
            return (trans_enthalpy - sum(pro_enthalpies)) * 0.0433641
        else:
            rct_enthalpies = [r.enthalpy for r in self.reactants]
            return (trans_enthalpy - sum(rct_enthalpies)) * 0.0433641

    def calculate_act_entropy(self, reverse=False):
        """
        Calculate entropy of activation.

        Args:
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            float: entropy of activation (in eV/K)

        """

        trans_entropy = self.transition_state.entropy

        if reverse:
            pro_entropies = [p.entropy for p in self.products]
            return (trans_entropy - sum(pro_entropies)) * 0.0000433641
        else:
            rct_entropies = [r.entropy for r in self.reactants]
            return (trans_entropy - sum(rct_entropies)) * 0.0000433641

    def calculate_act_gibbs(self, temperature=298.0, reverse=False):
        """
        Calculate Gibbs free energy of activation at a given temperature.

        ΔG = ΔH - T ΔS

        Args:
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            float: Gibbs free energy of activation (in eV)
        """

        act_energy = self.calculate_act_energy(reverse=reverse)
        act_enthalpy = self.calculate_act_enthalpy(reverse=reverse)
        act_entropy = self.calculate_act_entropy(reverse=reverse)

        return act_energy + act_enthalpy - temperature * act_entropy

    def calculate_act_thermo(self, temperature=298.0, reverse=False):
        """
        Calculate thermodynamics of activation for the reaction.

        Args:
            temperature (float): absolute temperature in Kelvin (default 300.0K)
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            act_thermo: dict with relevant activation thermodynamic variables
        """

        act_thermo = {"energy": self.calculate_act_energy(reverse=reverse),
                      "enthalpy": self.calculate_act_enthalpy(reverse=reverse),
                      "entropy": self.calculate_act_entropy(reverse=reverse),
                      "gibbs": self.calculate_act_gibbs(temperature, reverse=reverse)}

        return act_thermo

    def calculate_rate_constant(self, temperature=298.0, reverse=False, kappa=1.0):
        """
        Calculate the rate constant k by the Eyring-Polanyi equation of transition state theory.

        Args:
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction
            kappa (float): transmission coefficient (by default, we assume the assumptions of
                transition-state theory are valid, so kappa = 1.0

        Returns:
            k_rate (float): temperature-dependent rate constant
        """

        gibbs = self.calculate_act_gibbs(temperature=temperature, reverse=reverse)

        k_rate = kappa * k * temperature / h * np.exp(-gibbs / (8.617333262 * 10 ** -5 * temperature))
        return k_rate

    def calculate_rate(self, concentrations, temperature=298.0, reverse=False, kappa=1.0):
        """
        Calculate the based on the reaction stoichiometry.

        NOTE: Here, we assume that the reaction is an elementary step.

        Args:
            concentrations (list): concentrations of reactant molecules (product molecules, if
                reverse=True). Order of the reactants/products DOES matter.
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction
            kappa (float): transmission coefficient (by default, we assume the assumptions of
                transition-state theory are valid, so kappa = 1)

        Returns:
            rate (float): reaction rate, based on the stoichiometric rate law and the rate constant
        """

        rate_constant = self.calculate_rate_constant(temperature=temperature, reverse=reverse,
                                                     kappa=kappa)

        if reverse:
            exponents = np.array(list(self.rate_law["products"].values()))
        else:
            exponents = np.array(list(self.rate_law["reactants"].values()))

        rate = rate_constant * product(np.array(concentrations) ** exponents)

        return rate

    def __repr__(self):
        rct_str = " + ".join([r.molecule.composition.alphabetical_formula for r in self.reactants])
        pro_str = " + ".join([p.molecule.composition.alphabetical_formula for p in self.products])
        return "Rate Calculator for: {} --> {}".format(rct_str, pro_str)

    def __str__(self):
        return self.__repr__()


class BEPRateCalculator(ReactionRateCalculator):
    """
    A modified reaction rate calculator that uses the Bell-Evans-Polanyi principle to predict the
    activation energies (and, thus, the rate constants and reaction rates) of chemical reactions.

    The Bell-Evans-Polanyi principle states that, for reactions within a similar class or family,
    the difference in activation energy between the reactions is proportional to the difference in
    reaction enthalpy. That is,

    E_a = E_a,0 + alpha * ΔH, where

    E_a = the activation energy of the reaction of interest
    E_a,0 = the activation energy of some reference reaction in the same reaction family
    alpha = the location of the transition state along the reaction coordinate (0 <= alpha <= 1)
    ΔH = the enthalpy of reaction

    Whereas ReactionRateCalculator uses the Eyring equation, here we are forced to use collision
    theory to estimate reaction rates.

    Args:
        reactants (list): list of MoleculeEntry objects
        products (list): list of MoleculeEntry objects
        ea_reference (float): activation energy reference point (in eV)
        delta_h_reference (float): reaction enthalpy reference point (in eV)
        reaction (dict, or None): optional. If None (default), the "reactants" and
        "products" lists will serve as the basis for a Reaction object which represents the
        balanced stoichiometric reaction. Otherwise, this dict will show the number of molecules
        present in the reaction for each reactant and each product in the reaction.
        alpha (float): the reaction coordinate (must between 0 and 1)
    """

    def __init__(self, reactants, products, ea_reference, delta_h_reference,
                 alpha=0.5):

        self.ea_reference = ea_reference
        self.delta_h_reference = delta_h_reference
        self.alpha = alpha

        super().__init__(reactants, products, None)

    def calculate_act_energy(self, reverse=False):
        """
        Use the Bell-Evans-Polanyi principle to calculate the activation energy of the reaction.

        Args:
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            ea (float): the predicted energy of activation in eV
        """

        if reverse:
            enthalpy = -self.net_enthalpy
        else:
            enthalpy = self.net_enthalpy

        ea = self.ea_reference + self.alpha * (enthalpy - self.delta_h_reference)
        return ea

    def calculate_act_enthalpy(self, reverse=False):
        raise NotImplementedError("Method calculate_act_enthalpy is not valid for "
                                  "BEPRateCalculator,")

    def calculate_act_entropy(self, reverse=False):
        raise NotImplementedError("Method calculate_act_entropy is not valid for "
                                  "BEPRateCalculator,")

    def calculate_act_gibbs(self, temperature, reverse=False):
        raise NotImplementedError("Method calculate_act_gibbs is not valid for "
                                  "BEPRateCalculator,")

    def calculate_activation_thermo(self, temperature=298.0, reverse=False):
        raise NotImplementedError("Method calculate_activation_thermo is not valid for "
                                  "BEPRateCalculator,")

    def calculate_rate_constant(self, temperature=298.0, reverse=False, kappa=None):
        """
        Calculate the rate constant predicted by collision theory.

        Args:
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction
            kappa (None): not used for BEPRateCalculator

        Returns:
            k_rate (float): temperature-dependent rate constant
        """

        ea = self.calculate_act_energy(reverse=reverse)

        k_rate = np.exp(-ea / (8.617333262 * 10 ** -5 * temperature))

        return k_rate

    def calculate_rate(self, concentrations, temperature=298.0, reverse=False, kappa=1.0):
        """
        Calculate the rate using collision theory.

        Args:
            concentrations (list): concentrations of reactant molecules. Order of the reactants
                DOES matter.
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction
            kappa (float): here, kappa represents the steric factor (default 1.0, meaning that all
                collisions lead to appropriate conditions for a reaction

        Returns:
            rate (float): reaction rate, based on the stoichiometric rate law and the rate constant
        """

        k_rate = self.calculate_rate_constant(temperature=temperature, reverse=reverse)

        if reverse:
            exponents = np.array(list(self.rate_law["products"].values()))
            mols = [p.mol_graph.molecule for p in self.products]
        else:
            exponents = np.array(list(self.rate_law["reactants"].values()))
            mols = [r.mol_graph.molecule for r in self.reactants]

        masses = [m.composition.weight for m in mols]

        # Convert from Angstrom to m
        radius_factor = pi * sum([(np.max(mol.distance_matrix) * (10 ** -10) / 2) for mol in mols]) ** 2
        # Radius factor will be 0 for single atoms
        if radius_factor == 0:
            radius_factor = 1

        total_exponent = sum(exponents)
        number_prefactor = (1000 * N_A) ** total_exponent
        concentration_factor = product(np.array(concentrations) ** exponents)
        mass_factor = product(masses)/sum(masses) * amu_to_kg
        root_factor = np.sqrt(8 * k * temperature / (pi * mass_factor))

        z = number_prefactor * concentration_factor * radius_factor * root_factor

        rate = z * kappa * k_rate
        return rate


class ExpandedBEPRateCalculator(ReactionRateCalculator):
    """
    A modified reaction rate calculator that uses a modified version of the Bell-Evans-Polanyi
    principle to predict the Gibbs free energy of activation (and, thus, the rate constants and
    reaction rates) of chemical reactions.

    The Bell-Evans-Polanyi principle states that, for reactions within a similar class or family,
    the difference in activation energy between the reactions is proportional to the difference in
    reaction enthalpy. That is,

    E_a = E_a,0 + alpha * ΔH_rel, where

    E_a = the activation energy of the reaction of interest
    E_a,0 = the activation energy of some reference reaction in the same reaction family
    alpha = the location of the transition state along the reaction coordinate (0 <= alpha <= 1)
    ΔH_rel = ΔH - ΔH_0 = the difference in enthalpy change between the reaction of interest and the
        reference reaction

    Here, we assume that

    ΔG_a = ΔG_a,0 + alpha * (ΔG), where

    ΔG_a = the Gibbs free energy of activation for the reaction of interest
    ΔG_a,0 = the Gibbs free energy of activation of some reference reaction in the same reaction
        family
    alpha = the location of he transition state along the reaction coordinate (0 <= alpha <= 1)
    ΔG_rel = ΔG - ΔG_0 = the difference in Gibbs free energy change between the reaction of interest
        and the reference reaction.

    Args:
        reactants (list): list of MoleculeEntry objects
        products (list): list of MoleculeEntry objects
        delta_ea_reference (float): activation energy reference point (in eV)
        delta_ha_reference (float): activation enthalpy reference point (in eV)
        delta_sa_reference (float): activation entropy reference point (in eV/K)
        delta_e_reference (float): reaction energy reference point (in eV)
        delta_h_reference (float): reaction enthalpy reference point (in eV)
        delta_s_reference (float): reaction entropy reference point (in eV/K)
        reaction (dict, or None): optional. If None (default), the "reactants" and
        "products" lists will serve as the basis for a Reaction object which represents the
        balanced stoichiometric reaction. Otherwise, this dict will show the number of molecules
        present in the reaction for each reactant and each product in the reaction.
        alpha (float): the reaction coordinate (must between 0 and 1)
    """

    def __init__(self, reactants, products, delta_ea_reference, delta_ha_reference,
                 delta_sa_reference, delta_e_reference,
                 delta_h_reference, delta_s_reference, alpha=0.5):
        """

        """

        # Reference values for activation properties
        self.delta_ea_reference = delta_ea_reference
        self.delta_ha_reference = delta_ha_reference
        self.delta_sa_reference = delta_sa_reference

        # Reference values for net reaction properties
        self.delta_e_reference = delta_e_reference
        self.delta_h_reference = delta_h_reference
        self.delta_s_reference = delta_s_reference

        # Reaction coordinate
        self.alpha = alpha

        super().__init__(reactants, products, None)

    def calculate_act_energy(self, reverse=False):
        raise NotImplementedError("Method calculate_act_energy is not valid for "
                                  "ExpandedBEPRateCalculator,")

    def calculate_act_enthalpy(self, reverse=False):
        raise NotImplementedError("Method calculate_act_enthalpy is not valid for "
                                  "ExpandedBEPRateCalculator,")

    def calculate_act_entropy(self, reverse=False):
        raise NotImplementedError("Method calculate_act_entropy is not valid for "
                                  "ExpandedBEPCalculator,")

    def calculate_act_gibbs(self, temperature=298.0, reverse=False):
        """
        Calculate Gibbs free energy of activation at a given temperature.

        ΔG = ΔH - T ΔS

        Args:
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction

        Returns:
            delta_ga (float): Gibbs free energy of activation (in kcal/mol)
        """

        if reverse:
            delta_g = -self.calculate_net_gibbs(temperature)
        else:
            delta_g = self.calculate_net_gibbs(temperature)

        delta_g_ref = self.delta_e_reference + self.delta_h_reference - temperature * self.delta_s_reference
        delta_ga_ref = self.delta_ea_reference + self.delta_ha_reference - temperature * self.delta_sa_reference

        delta_ga = delta_ga_ref + self.alpha * (delta_g - delta_g_ref)

        return delta_ga

    def calculate_activation_thermo(self, temperature=298.0, reverse=False):
        raise NotImplementedError("Method calculate_activation_thermo is not valid for "
                                  "ExpandedBEPRateCalculator,")

    def calculate_rate_constant(self, temperature=298.0, reverse=False, kappa=1.0):
        """
        Calculate the rate constant k by the Eyring-Polanyi equation of transition state theory.

        Args:
            temperature (float): absolute temperature in Kelvin
            reverse (bool): if True (default False), consider the reverse reaction; otherwise,
                consider the forwards reaction
            kappa (float): transmission coefficient (by default, we assume the assumptions of
                transition-state theory are valid, so kappa = 1.0

        Returns:
            k_rate (float): temperature-dependent rate constant
        """

        # Convert eV to J/mol
        gibbs = self.calculate_act_gibbs(temperature=temperature, reverse=reverse)

        k_rate = kappa * k * temperature / h * np.exp(-gibbs / (8.617333262 * 10 ** -5 * temperature))
        return k_rate