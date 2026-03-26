# Releases and image tags

Images are published to **Docker Hub** as `erickuiper/suseobs-to-mattermost-webhook`.

## Automatic tags (CI)

| Event | Tags pushed | `APP_VERSION` in image |
|--------|-------------|-------------------------|
| Push to **`main`** | `latest`, `sha-<short>`, full `sha` | `0.1.0+<7-char-sha>` |
| Push git tag **`vX.Y.Z`** (semver) | `X.Y.Z`, `latest`, `sha-<short>`, full `sha` | `X.Y.Z` (no `v` prefix) |

The running app exposes **`GET /version`** with `version` and `git_sha` matching the build.

## Rolling out Kubernetes

**Do not rely only on `:latest`** — the cluster may not pull a new image if the tag string is unchanged.

Prefer an explicit version tag:

```yaml
image: docker.io/erickuiper/suseobs-to-mattermost-webhook:1.2.3
```

After CI finishes for tag `v1.2.3`, use image tag **`1.2.3`** (or **`sha-<short>`** from the same workflow run).

## Cut a release

1. Ensure `main` is green.
2. Create and push an annotated tag (semver):

   ```bash
   git checkout main
   git pull
   git tag -a v1.2.3 -m "Release v1.2.3"
   git push origin v1.2.3
   ```

3. Wait for the **CI** workflow; confirm the new tag on [Docker Hub](https://hub.docker.com/r/erickuiper/suseobs-to-mattermost-webhook/tags).
4. Update your deployment manifest with `image: ...:1.2.3` and apply (or bump a Helm value).

Tags must match **`v*.*.*`** (e.g. `v1.0.0`) so Docker metadata can apply semver tagging.
