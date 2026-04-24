# Cube Message Devtools

Standalone Cube message utilities copied from the production API shape.
They read Cube settings from `.env` or an explicit env file, build compatible
payloads, and send directly with `httpx` without importing `api.config`.

## multiMessage

```bash
python -m devtools.cube_message.multimessage \
  --user-id cube.user \
  --message "hello" \
  --dry-run
```

Remove `--dry-run` to send the request to `CUBE_MULTIMESSAGE_URL`.

## richnotification

```bash
python -m devtools.cube_message.richnotification \
  --user-id cube.user \
  --channel-id cube.channel \
  --message "hello" \
  --dry-run
```

Remove `--dry-run` to send the request to `CUBE_RICHNOTIFICATION_URL`.

## Import Usage

```python
from devtools.cube_message.multimessage import send_multimessage
from devtools.cube_message.richnotification import blocks, send_richnotification_blocks

send_multimessage(user_id="cube.user", reply_message="hello")

send_richnotification_blocks(
    blocks.add_text("hello"),
    user_id="cube.user",
    channel_id="cube.channel",
)
```
