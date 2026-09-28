import logging
from typing import Dict, Any, Tuple
from jinja2 import Environment, BaseLoader, select_autoescape, Undefined

logger = logging.getLogger("worker.template_engine")


class SilentUndefined(Undefined):
    """Custom undefined handler that renders empty string instead of raising error."""
    def _fail_with_undefined_error(self, *args, **kwargs):
        return ""

    def __str__(self):
        return ""


class TemplateEngine:
    def __init__(self):
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=False,
            ),
            undefined=SilentUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._register_custom_filters()

    def _register_custom_filters(self):
        def currency_filter(value, symbol="$"):
            try:
                return f"{symbol}{float(value):,.2f}"
            except (ValueError, TypeError):
                return f"{symbol}{value}"

        self.env.filters["currency"] = currency_filter

    def render(
        self,
        subject_template: str,
        body_template: str,
        dynamic_data: Dict[str, Any],
    ) -> Tuple[str, str]:
        """
        Render subject and body templates using dynamic data dictionary.
        
        Returns:
            Tuple[rendered_subject, rendered_body]
        """
        try:
            subject_tmpl = self.env.from_string(subject_template)
            rendered_subject = subject_tmpl.render(**dynamic_data)

            body_tmpl = self.env.from_string(body_template)
            rendered_body = body_tmpl.render(**dynamic_data)

            return rendered_subject.strip(), rendered_body.strip()
        except Exception as e:
            logger.error(f"Template rendering failed: {e}", exc_info=True)
            raise


template_engine = TemplateEngine()
