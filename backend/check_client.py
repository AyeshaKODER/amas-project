from app.utils.docker_client import get_docker_client
c = get_docker_client()
print("CLIENT_TYPE->", type(c))
try:
    # high-level client has .version(); APIClient may not, so guard it
    ver = getattr(c, "version", None)
    if callable(ver):
        print("CLIENT_VERSION->", ver())
    else:
        # try low-level APIClient ping/info
        try:
            print("APICLIENT_INFO->", c.version())
        except Exception as e:
            print("APICLIENT_ERR->", repr(e))
except Exception as e:
    print("GET_CLIENT_ERROR->", repr(e))
