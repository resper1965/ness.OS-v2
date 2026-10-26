"""Local-only Zabbix/GLPI HTTP double for the disposable Hub runtime test."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit


class Handler(BaseHTTPRequestHandler):
    tickets = []
    fail_next_ticket_response = False

    def reply(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/state":
            self.reply(
                200,
                {
                    "ticket_count": len(self.tickets),
                    "ticket_names": [ticket["name"] for ticket in self.tickets],
                    "unsafe_html": any(
                        "<script>" in ticket["content"] for ticket in self.tickets
                    ),
                },
            )
        elif url.path == "/apirest.php/initSession":
            self.reply(200, {"session_token": "local", "session": {"glpiID": 94}})
        elif url.path == "/apirest.php/Ticket/":
            marker = parse_qs(url.query).get("searchText[name]", [""])[0]
            self.reply(200, [t for t in self.tickets if marker in t["name"]])
        elif url.path == "/apirest.php/killSession":
            self.reply(200, True)
        else:
            self.reply(404, {"error": "unknown path"})

    def do_POST(self):
        path = urlsplit(self.path).path
        data = self.body()
        if path == "/api_jsonrpc.php":
            if self.headers.get("Authorization") != "Bearer local-zabbix-token":
                self.reply(403, {"error": "unauthorized"})
            elif data.get("method") == "host.get":
                self.reply(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": data["id"],
                        "result": [
                            {
                                "hostid": data["params"]["hostids"][0],
                                "hostgroups": [{"name": "[ Cavan ]"}],
                            }
                        ],
                    },
                )
            else:
                self.reply(400, {"error": "unexpected method"})
        elif path == "/control/fail-next-ticket-response":
            type(self).fail_next_ticket_response = True
            self.reply(200, {"armed": True})
        elif path == "/apirest.php/changeActiveEntities":
            if data == {"entities_id": 8, "is_recursive": False}:
                self.reply(200, True)
            else:
                self.reply(403, False)
        elif path == "/apirest.php/Ticket":
            ticket = {"id": 501 + len(self.tickets), **data["input"]}
            self.tickets.append(ticket)
            if self.fail_next_ticket_response:
                type(self).fail_next_ticket_response = False
                self.reply(502, {"error": "synthetic response loss"})
            else:
                self.reply(201, {"id": ticket["id"]})
        elif path == "/apirest.php/ITILFollowup":
            self.reply(201, {"id": 601})
        else:
            self.reply(404, {"error": "unknown path"})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
