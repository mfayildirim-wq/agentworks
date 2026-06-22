# nginx-proxy vhost snippets

This deployment expects a shared `nginx-proxy` container (image
`nginxproxy/nginx-proxy`) that already runs on the host and routes one or more
sites via the `proxy-net` network (see `docker-compose.prod.yml`). That proxy is
**not** part of this Compose file.

Some `nginx-proxy` template versions do **not** emit `client_max_body_size` from
the `CLIENT_MAX_BODY_SIZE` container env. In that case the upload limit is set via
a per-vhost snippet placed into the proxy's `vhost.d` volume
(`/etc/nginx/vhost.d/`). The snippet must be named exactly after your public
domain.

`example.com.snippet` in this folder contains the upload-limit directive
(`client_max_body_size 26m;`, just above the backend's 25 MB limit so the API can
return a friendly "max 25 MB" message instead of a raw 413).

## Deploy the snippet

Replace `your-domain.example.com` with your actual `PUBLIC_DOMAIN`:

```bash
# Copy the snippet into the nginx-proxy volume (filename = your domain) …
docker cp infra/nginx-vhost.d/example.com.snippet \
  nginx-proxy:/etc/nginx/vhost.d/your-domain.example.com
# … trigger docker-gen to regenerate (adds the `include` line to the server block) …
PID=$(docker exec nginx-proxy sh -c 'for p in /proc/[0-9]*; do grep -qa docker-gen "$p/cmdline" 2>/dev/null && echo "${p#/proc/}"; done' | head -1)
docker exec nginx-proxy sh -c "kill -HUP $PID"
# … and verify:
docker exec nginx-proxy nginx -t
curl -s -o /dev/null -w '%{http_code}\n' https://your-domain.example.com/
```

The `include /etc/nginx/vhost.d/your-domain.example.com;` only appears in the
server block if the file exists **at docker-gen generation time** — hence the HUP
after copying.
