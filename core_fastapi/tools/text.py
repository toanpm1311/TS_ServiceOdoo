import re


def is_url(string):
    # Regular expression pattern to match a URL
    url_pattern = re.compile(
        r'^(https?|ftp):\/\/'  # scheme (http, https, ftp)
        r'([a-zA-Z0-9.-]+)'    # domain
        r'(:[0-9]{1,5})?'      # port (optional)
        r'(\/.*)?$'            # path (optional)
    )

    return re.match(url_pattern, string) is not None
