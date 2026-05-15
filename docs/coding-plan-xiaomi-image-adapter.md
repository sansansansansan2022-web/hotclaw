# Xiaomi Coding Plan - Image Generation Adapter

## Goal

Make image generation configuration more fault-tolerant for OpenAI-compatible gateways and reduce misconfiguration failures during setup/testing.

## Scope

- Backend image-generation connection test path
- Backend runtime image-generation request path
- Documentation for rollout and validation

## Implemented in this round

1. Normalize OpenAI-compatible image endpoint
   - If configured base URL ends with `/chat/completions`, automatically map it to `/images/generations`.
   - Applied in runtime image generation service.

2. Adapt connection probe behavior
   - For OpenAI-compatible providers (`openai/custom/volcengine`), probe now:
     - derives `/models` from `/chat/completions` when needed
     - posts test payload to normalized image endpoint
   - This prevents common setup mistakes from failing with misleading schema errors.

## Validation checklist

- [ ] Save config with base URL mistakenly set to `/chat/completions`
- [ ] Run `Test Connection` in settings
- [ ] Confirm request is routed to `/images/generations`
- [ ] Confirm no `messages: Field required` error

## Follow-ups

1. Add dedicated preset for specific gateway brands if model catalog is known.
2. Add explicit UI hint: image generation requires an image endpoint, not chat completion endpoint.
3. Add unit tests for endpoint normalization in:
   - `system_config_routes`
   - `image_generation_service`
