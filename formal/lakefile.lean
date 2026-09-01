import Lake
open Lake DSL

package «fpl-formal» where
  leanOptions := #[
    ⟨`autoImplicit, false⟩,
    ⟨`relaxedAutoImplicit, false⟩
  ]

@[default_target]
lean_lib FPL where
  roots := #[`FPL]
