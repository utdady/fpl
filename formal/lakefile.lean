import Lake
open Lake DSL

package fpl_formal where
  leanOptions := #[
    ⟨`autoImplicit, false⟩,
    ⟨`relaxedAutoImplicit, false⟩
  ]

@[default_target]
lean_lib FPL where
  roots := #[`FPL]
