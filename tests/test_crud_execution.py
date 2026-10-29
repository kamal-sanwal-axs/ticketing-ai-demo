import unittest

from apex_rag_demo.crud_policy import mutation_executes_live, WriteKind, write_kind_for_intent


class CrudExecutionPolicyTests(unittest.TestCase):
    def test_reads_never_live_mutation(self) -> None:
        self.assertFalse(
            mutation_executes_live("marketing_events", mutations_dry_run=False),
        )

    def test_create_live_by_default(self) -> None:
        self.assertTrue(
            mutation_executes_live("create_organization", mutations_dry_run=False),
        )

    def test_update_needs_confirm(self) -> None:
        self.assertFalse(
            mutation_executes_live("update_event", mutations_dry_run=False, confirm_mutation=False),
        )
        self.assertTrue(
            mutation_executes_live("update_event", mutations_dry_run=False, confirm_mutation=True),
        )

    def test_global_dry_run_blocks_create(self) -> None:
        self.assertFalse(
            mutation_executes_live("create_event", mutations_dry_run=True),
        )

    def test_reset_live_without_confirm(self) -> None:
        self.assertEqual(write_kind_for_intent("reset_inventory_publish"), WriteKind.RESET)
        self.assertTrue(
            mutation_executes_live("reset_inventory_publish", mutations_dry_run=False),
        )


if __name__ == "__main__":
    unittest.main()
