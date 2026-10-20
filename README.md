# incubrix-broll-engine

## Scene image generation

The worker generates one 16:9 PNG still per scene alongside the existing stock
footage selection and AI video-clip fallback. Images are written to
`IMAGE_OUTPUT_DIR/<job-id>/scene_<index>.png`; Docker Compose mounts the default
`outputs/` directory from the project into the worker.

The default `IMAGE_PROVIDER=mock` keeps local and test runs offline. To use
OpenAI, set `IMAGE_PROVIDER=openai` and provide `OPENAI_API_KEY` in `.env`.
`OPENAI_IMAGE_MODEL` defaults to `gpt-image-1`. The provider requests the
1536x1024 landscape size and center-crops the result to 16:9. Image paths,
dimensions, MIME type, and provider are included for each scene in the timeline.
Final video rendering is not performed.