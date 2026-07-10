package guardian

default allow = true
default deny = false

# Block any LLM response that contains action fields.
# The honesty boundary: the LLM interprets objectives, never actions.

deny {
    input.response.action_type
}

deny {
    input.response.parameters
}

deny {
    input.response.replicas
}

deny {
    input.response.action_plan
}

deny {
    input.response.action_step
}

allow {
    not deny
}
