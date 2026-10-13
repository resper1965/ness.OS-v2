"""Load root-only GLPI secrets, then serve as the unprivileged image user."""

import os
import pwd

import uvicorn

from app.integrations.glpi_maintenance_runtime import build_app


def main():
    if os.geteuid() != 0:
        raise RuntimeError("GLPI maintenance gateway must start as root")

    app = build_app()
    user = pwd.getpwnam("nessops")
    os.setgroups([])
    os.setgid(user.pw_gid)
    os.setuid(user.pw_uid)
    if os.geteuid() != user.pw_uid or os.getegid() != user.pw_gid:
        raise RuntimeError("GLPI maintenance gateway could not drop privileges")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
