from pathlib import Path

import esphome.codegen as cg
import esphome.config_validation as cv

CODEOWNERS = ["@vithurshanselvarajah"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    # Make this component directory visible to the compiler so the header can be
    # included regardless of where the dashboard config lives.
    component_dir = Path(__file__).resolve().parent
    cg.add_build_flag(f'-I"{component_dir.as_posix()}"')
    cg.add_global(cg.RawStatement('#include "fingerprint_backup.h"'))
