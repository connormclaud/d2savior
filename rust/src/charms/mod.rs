mod dp;
mod dps;
mod exact;
mod greedy;
mod solver;

pub(crate) use solver::CharmSolver;

#[cfg(test)]
use crate::eval::eval_build_summary;
#[cfg(test)]
use crate::search::score_eval_summary;
#[cfg(test)]
use crate::types::{
    BuildConstraints, CharmSpec, HandWeapon, ItemSpec, OffenseProfile, SearchMode, Stats,
};
#[cfg(test)]
use greedy::{charm_stat_ub, greedy_charms, greedy_charms_pass, shrink_charm_pool};

#[cfg(test)]
#[path = "../charms_tests.rs"]
mod tests;
