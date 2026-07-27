

def test_heal_and_break_require_privileged_actors(system) -> None:
    """Entity-seat fable5 P0-1 (2026-07-25): heal_scar/break_bond engraved
    whatever actor a caller claimed while revalue validated — one rule,
    three verbs now (amplitude-authority discipline: deliberate
    revaluation of standing experience is a reflective act)."""
    import pytest

    owner = "entity:guard"
    scar_ids = system.appraise(
        "person:rival", sign=-1, magnitude=9.0, scar=True,
        reason="a betrayal", scope="life", owner_id=owner,
        actor="entity-reflection")
    scar_event = next(i for i in scar_ids if ":" in i or i)
    with pytest.raises(ValueError, match="privileged actor"):
        system.heal_scar(scar_ids[-1], reason="workplace trying to heal",
                         scope="life", owner_id=owner, actor="workplace:visit-9")
    bond_ids = system.appraise(
        "person:friend", sign=1, magnitude=9.0, bond=True,
        reason="a formative kindness", scope="life", owner_id=owner,
        actor="entity-reflection")
    with pytest.raises(ValueError, match="privileged actor"):
        system.break_bond(bond_ids[-1], reason="workplace trying to break",
                          scope="life", owner_id=owner, actor="workplace:visit-9")
    # The entity's own reflection still heals (the legitimate lane).
    healed = system.heal_scar(scar_ids[-1], reason="the lesson formed",
                              scope="life", owner_id=owner,
                              actor="entity-reflection")
    assert healed
