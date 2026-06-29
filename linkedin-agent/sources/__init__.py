"""Data source plugins.

Importing this package registers all built-in sources. To add a source: create
a module, subclass BaseSource, decorate with @register_source("name"), and
import it below. Enable/disable and parameterise sources in config/sources.yaml
— never hardcode sources in agent code.
"""

from . import (  # noqa: F401  (imported for registration side-effect)
    rss_source,
    url_source,
    apify_source,
    blog_source,
    news_source,
    github_source,
)
