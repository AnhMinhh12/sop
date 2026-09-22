"""SOP engine registration for product KOR-H2110."""

from importlib import import_module


# The legacy engine module begins with a number, so it must be loaded
# dynamically instead of through a normal ``from ... import`` statement.
BaseKOREngine = import_module(
    "projects.sop_monitoring.core.engines.639957_engine"
).ProductEngine


class ProductEngine(BaseKOREngine):
    """Run the three-step KOR-H2110 SOP used by machine 9."""

    def __init__(self, sop_config: dict):
        super().__init__(sop_config)
        self.product_id = "KOR-H2110"
        self._product_seen_in_mold = False
        self._hand_seen_after_product = False

    def reset(self, now: float = None) -> None:
        """Reset the inherited FSM and the product-removal preconditions."""
        super().reset(now=now)
        self._product_seen_in_mold = False
        self._hand_seen_after_product = False

    def _check_step_logic(
        self,
        step: dict,
        now: float,
        update_status: bool = True,
        centroid_only: bool = False,
    ) -> bool:
        """Require product-present → hand-in-mold → product-absent for step 1."""
        if step.get("logic") != "take_product_from_mold":
            return super()._check_step_logic(step, now, update_status, centroid_only)

        mold_zone = step["required_zone"]
        product_in_mold = self._is_object_in_zone(self.last_products, mold_zone)
        hand_in_mold = any(
            self._is_in_zone(side, mold_zone, centroid_only=centroid_only)
            for side in ("left", "right")
        )

        if product_in_mold:
            self._product_seen_in_mold = True

        if self._product_seen_in_mold and hand_in_mold:
            self._hand_seen_after_product = True

        return (
            self._product_seen_in_mold
            and self._hand_seen_after_product
            and not product_in_mold
        )
