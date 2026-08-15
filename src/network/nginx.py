"""
Nginx configuration management.
"""
import os
from jinja2 import Template
from ..utils.shell import run, ensure_dir
from ..core.state import InstallState


def write_site(name: str, content: str, state: InstallState = None) -> None:
    ensure_dir("/etc/nginx/sites-available")
    ensure_dir("/etc/nginx/sites-enabled")

    avail = f"/etc/nginx/sites-available/{name}"
    enabled = f"/etc/nginx/sites-enabled/{name}"

    with open(avail, "w") as f:
        f.write(content)

    if os.path.exists(enabled):
        os.remove(enabled)
    os.symlink(avail, enabled)

    if state:
        state.add_nginx(name)
        state.add_file(avail)


def render_cdn_origin(xray_port: int, xhttp_path: str, ssl_cert: str, ssl_key: str,
                      ipv6: bool = True, panel_path: str = None, panel_port: int = None) -> str:
    template_path = os.path.join(os.path.dirname(__file__), "../../templates/nginx/cdn_origin.conf.j2")
    with open(template_path) as f:
        template = Template(f.read())

    return template.render(
        xray_port=xray_port,
        xhttp_path=xhttp_path,
        ssl_cert=ssl_cert,
        ssl_key=ssl_key,
        ipv6=ipv6,
        panel_path=panel_path,
        panel_port=panel_port
    )


def reload(state: InstallState = None) -> None:
    r = run("nginx -t && systemctl restart nginx", check=False)
    if r.ok:
        print("  ✅ Nginx перезапущен")
        if state:
            state.add_step("nginx:reloaded")
    else:
        print(f"  ❌ Ошибка nginx: {r.stderr[:200]}")
        raise RuntimeError("nginx config test failed")


def setup(state: InstallState) -> None:
    ensure_dir("/var/www/html")
    decoy = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Website</title>
<style>body{margin:0;height:100vh;display:flex;justify-content:center;align-items:center;background:#2c2825;color:#e3d9c6;font-family:Georgia,serif;}</style>
</head>
<body><div style="text-align:center;"><h1>Coming Soon</h1></div></body>
</html>"""
    with open("/var/www/html/index.html", "w") as f:
        f.write(decoy)
    state.add_file("/var/www/html/index.html")
