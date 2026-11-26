mod charms;
mod eval;
mod search;
mod types;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
pub use eval::{class_breakpoints, evaluate_build};
pub use eval::{blizzard_damage, blizzard_damage_with_base, evaluate_build_core};
#[cfg(feature = "python")]
pub use search::{optimize_builds, score_of_result};
pub use search::{
    ScoreTuple, optimize_builds_core, optimize_builds_with_baseline, score_of_result_core,
};
pub use types::{
    BuildConstraints, BuildResult, CasterSkillModel, CharacterStats, CharmSpec, ItemSpec,
    MeleeSkillModel, SkillModel, TargetProfile,
};

#[cfg(feature = "python")]
#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ItemSpec>()?;
    m.add_class::<CharmSpec>()?;
    m.add_class::<CharacterStats>()?;
    m.add_class::<TargetProfile>()?;
    m.add_class::<CasterSkillModel>()?;
    m.add_class::<MeleeSkillModel>()?;
    m.add_class::<BuildConstraints>()?;
    m.add_class::<BuildResult>()?;
    m.add_function(wrap_pyfunction!(evaluate_build, m)?)?;
    m.add_function(wrap_pyfunction!(optimize_builds, m)?)?;
    m.add_function(wrap_pyfunction!(score_of_result, m)?)?;
    m.add_function(wrap_pyfunction!(blizzard_damage, m)?)?;
    m.add_function(wrap_pyfunction!(blizzard_damage_with_base, m)?)?;
    m.add_function(wrap_pyfunction!(class_breakpoints, m)?)?;
    Ok(())
}
