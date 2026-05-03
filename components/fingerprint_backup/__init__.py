import esphome.config_validation as cv

CODEOWNERS = ["@vithurshanselvarajah"]

CONFIG_SCHEMA = cv.Schema({})


async def to_code(config):
    # Header is auto-included via esphome.h for this component.
    return
