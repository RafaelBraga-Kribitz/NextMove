"""Content-hash lineage: every derived table records the content hashes of its inputs and
the hash of the config that generated it, and the chain is printable (DATA-04).
"""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

import nextmove.storage as st
import nextmove.storage.repository as repository_module
from nextmove.config.loader import load_config
from nextmove.storage.lineage import LineageRecordDraft, content_hash, record_lineage


class Row(BaseModel):
    sku: str
    qty: int


@pytest.fixture
def resolved_config():
    return load_config("tiny")


def _write(root, name, zone, stage, rc, sku="a", input_paths=()):
    return st.write_table(
        [Row(sku=sku, qty=1)],
        name,
        zone,
        ("sku",),
        rc,
        stage,
        input_paths=list(input_paths),
        root=root,
    )


# --------------------------------------------------------------------------------------
# content_hash
# --------------------------------------------------------------------------------------


def test_content_hash_is_64_char_lowercase_sha256(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello world")
    h = content_hash(f)
    assert len(h) == 64
    assert h == h.lower()
    assert all(c in "0123456789abcdef" for c in h)


# --------------------------------------------------------------------------------------
# record_lineage basics
# --------------------------------------------------------------------------------------


def test_input_hashes_sorted_lexicographically_regardless_of_supplied_order(
    tmp_path, resolved_config
):
    root = tmp_path
    p1 = _write(root, "in1", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config, sku="a")
    p2 = _write(root, "in2", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config, sku="zzz")
    derived = st.write_table(
        [Row(sku="d", qty=1)],
        "derived",
        st.Zone.FEATURES,
        ("sku",),
        resolved_config,
        st.Stage.FEATURES,
        input_paths=[p2, p1],  # deliberately reversed order
        root=root,
    )
    lineage = st.read_lineage(root=root)
    rec = next(r for r in lineage if r.table_name == "derived")
    assert rec.input_hashes == sorted(rec.input_hashes)
    expected = sorted([content_hash(p1), content_hash(p2)])
    assert rec.input_hashes == expected
    assert derived.is_file()


def test_no_inputs_stores_empty_list_not_null(tmp_path, resolved_config):
    p = _write(tmp_path, "root_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    lineage = st.read_lineage(root=tmp_path)
    rec = next(r for r in lineage if r.table_name == "root_tbl")
    assert rec.input_tables == []
    assert rec.input_hashes == []
    assert p.is_file()


def test_record_lineage_upserts_no_duplicate_row(tmp_path, resolved_config):
    root = tmp_path
    _write(root, "upsert_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    _write(root, "upsert_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    lineage = [r for r in st.read_lineage(root=root) if r.table_name == "upsert_tbl"]
    assert len(lineage) == 1


def test_two_tables_from_identical_inputs_keep_two_rows(tmp_path, resolved_config):
    root = tmp_path
    shared_input = _write(root, "shared_input", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    st.write_table(
        [Row(sku="s1", qty=1)],
        "sibling_a",
        st.Zone.FEATURES,
        ("sku",),
        resolved_config,
        st.Stage.FEATURES,
        input_paths=[shared_input],
        root=root,
    )
    st.write_table(
        [Row(sku="s2", qty=1)],
        "sibling_b",
        st.Zone.FEATURES,
        ("sku",),
        resolved_config,
        st.Stage.FEATURES,
        input_paths=[shared_input],
        root=root,
    )
    lineage = st.read_lineage(root=root)
    names = {r.table_name for r in lineage}
    assert {"sibling_a", "sibling_b"} <= names
    rec_a = next(r for r in lineage if r.table_name == "sibling_a")
    rec_b = next(r for r in lineage if r.table_name == "sibling_b")
    assert rec_a.input_hashes == rec_b.input_hashes
    assert rec_a is not rec_b


def test_record_lineage_writes_only_its_own_stage_fragment(tmp_path, resolved_config):
    root = tmp_path
    _write(root, "ingest_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    _write(root, "feature_tbl", st.Zone.FEATURES, st.Stage.FEATURES, resolved_config)

    ingest_fragment = root / "lineage" / "ingest.parquet"
    features_fragment = root / "lineage" / "features.parquet"
    before_ingest_bytes = ingest_fragment.read_bytes()

    _write(root, "feature_tbl_2", st.Zone.FEATURES, st.Stage.FEATURES, resolved_config)

    assert ingest_fragment.read_bytes() == before_ingest_bytes
    assert features_fragment.is_file()


def test_record_lineage_content_hash_tracks_disk_not_caller_claim(tmp_path, resolved_config):
    root = tmp_path
    path = _write(root, "mutate_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    draft = LineageRecordDraft(
        table_name="mutate_tbl",
        zone="canonical",
        input_tables=[],
        config_hash=resolved_config.config_hash,
        contract_version="1.0.0",
        producer_stage=st.Stage.INGEST,
        row_count=1,
    )
    path.write_bytes(path.read_bytes() + b"TAMPERED")
    record = record_lineage(path, draft, [], root=root)
    assert record.content_hash == content_hash(path)


def test_recording_lineage_produces_no_further_lineage_row(tmp_path, resolved_config, monkeypatch):
    calls = {"n": 0}
    real = repository_module._record_lineage

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(repository_module, "_record_lineage", _counting)
    _write(tmp_path, "term_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    assert calls["n"] == 1


def test_record_lineage_called_directly_returns_without_recursion(tmp_path, resolved_config):
    path = st.write_table(
        [Row(sku="a", qty=1)],
        "direct_tbl",
        st.Zone.CANONICAL,
        ("sku",),
        resolved_config,
        st.Stage.INGEST,
        root=tmp_path,
        record_lineage=False,
    )
    draft = LineageRecordDraft(
        table_name="direct_tbl",
        zone="canonical",
        input_tables=[],
        config_hash=resolved_config.config_hash,
        contract_version="1.0.0",
        producer_stage=st.Stage.INGEST,
        row_count=1,
    )
    record = record_lineage(path, draft, [], root=tmp_path)
    assert record.table_name == "direct_tbl"
    fragment = tmp_path / "lineage" / "ingest.parquet"
    table = st.read_table("ingest", st.Zone.LINEAGE, root=tmp_path)
    assert table.num_rows == 1
    assert fragment.is_file()


# --------------------------------------------------------------------------------------
# print_lineage_chain
# --------------------------------------------------------------------------------------


def test_print_lineage_chain_root_node_no_raise(tmp_path, resolved_config):
    _write(tmp_path, "lonely_root", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    rendered = st.print_lineage_chain("lonely_root", root=tmp_path)
    assert "lonely_root" in rendered


def test_print_lineage_chain_multi_hop_spans_fragments(tmp_path, resolved_config):
    root = tmp_path
    leaf_input = _write(root, "leaf_input", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    mid = st.write_table(
        [Row(sku="m", qty=1)],
        "mid_tbl",
        st.Zone.FEATURES,
        ("sku",),
        resolved_config,
        st.Stage.FEATURES,
        input_paths=[leaf_input],
        root=root,
    )
    assert mid.is_file()
    rendered = st.print_lineage_chain("mid_tbl", root=root)
    assert "mid_tbl" in rendered
    assert "leaf_input" in rendered


def test_print_lineage_chain_deterministic_across_calls(tmp_path, resolved_config):
    _write(tmp_path, "det_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    first = st.print_lineage_chain("det_tbl", root=tmp_path)
    second = st.print_lineage_chain("det_tbl", root=tmp_path)
    assert first == second


def test_print_lineage_chain_raises_on_cycle(tmp_path, resolved_config):
    root = tmp_path
    p_a = st.write_table(
        [Row(sku="a", qty=1)],
        "cyc_a",
        st.Zone.CANONICAL,
        ("sku",),
        resolved_config,
        st.Stage.INGEST,
        root=root,
        record_lineage=False,
    )
    p_b = st.write_table(
        [Row(sku="b", qty=1)],
        "cyc_b",
        st.Zone.CANONICAL,
        ("sku",),
        resolved_config,
        st.Stage.INGEST,
        root=root,
        record_lineage=False,
    )
    draft_a = LineageRecordDraft(
        table_name="cyc_a",
        zone="canonical",
        input_tables=["cyc_b"],
        config_hash=resolved_config.config_hash,
        contract_version="1.0.0",
        producer_stage=st.Stage.INGEST,
        row_count=1,
    )
    draft_b = LineageRecordDraft(
        table_name="cyc_b",
        zone="canonical",
        input_tables=["cyc_a"],
        config_hash=resolved_config.config_hash,
        contract_version="1.0.0",
        producer_stage=st.Stage.INGEST,
        row_count=1,
    )
    record_lineage(p_a, draft_a, [p_b], root=root)
    record_lineage(p_b, draft_b, [p_a], root=root)
    with pytest.raises(ValueError, match="cycle"):
        st.print_lineage_chain("cyc_a", root=root)


# --------------------------------------------------------------------------------------
# read_lineage ordering
# --------------------------------------------------------------------------------------


def test_read_lineage_iterates_stage_enum_not_directory_listing(tmp_path, resolved_config):
    root = tmp_path
    _write(root, "ordered_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    lineage_dir = root / "lineage"
    (lineage_dir / "not_a_stage.parquet").write_bytes(b"not a real fragment")
    records = st.read_lineage(root=root)
    assert all(r.table_name != "not_a_stage" for r in records)


# --------------------------------------------------------------------------------------
# Fragment ownership (HIGH-3)
# --------------------------------------------------------------------------------------


def test_fragment_isolation_one_file_per_stage(tmp_path, resolved_config):
    root = tmp_path
    _write(root, "sim_tbl", st.Zone.RAW, st.Stage.SIMULATE, resolved_config)
    _write(root, "ing_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    _write(root, "feat_tbl", st.Zone.FEATURES, st.Stage.FEATURES, resolved_config)

    lineage_dir = root / "lineage"
    fragment_files = sorted(p.name for p in lineage_dir.glob("*.parquet"))
    assert fragment_files == ["features.parquet", "ingest.parquet", "simulate.parquet"]

    canonical_dir = root / "canonical"
    assert not any(p.suffix == ".parquet" and "lineage" in p.stem for p in canonical_dir.glob("*"))
    assert not (canonical_dir / "lineage.parquet").exists()

    ingest_bytes_before = (lineage_dir / "ingest.parquet").read_bytes()
    simulate_bytes_before = (lineage_dir / "simulate.parquet").read_bytes()
    _write(root, "feat_tbl_2", st.Zone.FEATURES, st.Stage.FEATURES, resolved_config)
    assert (lineage_dir / "ingest.parquet").read_bytes() == ingest_bytes_before
    assert (lineage_dir / "simulate.parquet").read_bytes() == simulate_bytes_before


def test_canonical_zone_holds_no_lineage_file(tmp_path, resolved_config):
    root = tmp_path
    _write(root, "canon_tbl", st.Zone.CANONICAL, st.Stage.INGEST, resolved_config)
    canonical_dir = root / "canonical"
    assert not (canonical_dir / "lineage.parquet").exists()
    assert not any("lineage" in p.name for p in canonical_dir.glob("*"))


# --------------------------------------------------------------------------------------
# Import acyclicity (HIGH-2) -- fresh-interpreter subprocess proof
# --------------------------------------------------------------------------------------

_SRC_DIR = str(Path(__file__).resolve().parents[2] / "src")


@pytest.mark.slow
def test_lineage_module_imports_cleanly_standalone():
    script = (
        f"import sys; sys.path.insert(0, {_SRC_DIR!r}); "
        "import nextmove.storage.lineage; print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


@pytest.mark.slow
def test_private_parquet_module_imports_cleanly_standalone():
    script = (
        f"import sys; sys.path.insert(0, {_SRC_DIR!r}); "
        "import nextmove.storage._parquet; print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"


def test_lineage_module_does_not_import_repository():
    lineage_src = (Path(_SRC_DIR) / "nextmove" / "storage" / "lineage.py").read_text()
    import re

    matches = re.findall(r"^[ \t]*(from|import)[ \t].*repository", lineage_src, flags=re.MULTILINE)
    assert matches == []


# --------------------------------------------------------------------------------------
# dvc.yaml not yet owned by this plan
# --------------------------------------------------------------------------------------


def test_dvc_yaml_does_not_exist_yet():
    repo_root = Path(_SRC_DIR).parent
    assert not (repo_root / "dvc.yaml").exists()
