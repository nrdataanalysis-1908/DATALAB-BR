"""Generate a standalone HTML report from the locally discovered TSE CKAN catalog.

The report describes catalog metadata only. It does not calculate electoral results.
"""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_datasets(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("datasets", [])
    if not isinstance(entries, list):
        raise ValueError("manifest.datasets must be a list")

    datasets: list[dict[str, Any]] = []
    base = manifest_path.parent.resolve()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("path")
        if not isinstance(filename, str) or not filename.endswith(".json") or Path(filename).name != filename:
            continue
        target = (base / filename).resolve()
        if target.parent != base or not target.is_file():
            continue
        try:
            item = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            datasets.append(item)
    return manifest, datasets


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def build_report(manifest_path: Path, output_path: Path) -> Path:
    manifest_path = manifest_path.resolve()
    output_path = output_path.resolve()
    if manifest_path.is_file():
        manifest, datasets = load_datasets(manifest_path)
        status = "CATÁLOGO CARREGADO"
        generated_at = manifest.get("discovered_at") or "Não informado"
        source = manifest.get("source_url") or "https://dadosabertos.tse.jus.br/"
    else:
        manifest, datasets = {}, []
        status = "AGUARDANDO DESCOBERTA"
        generated_at = "Ainda não gerado"
        source = "https://dadosabertos.tse.jus.br/"

    formats: Counter[str] = Counter()
    organizations: Counter[str] = Counter()
    rows: list[str] = []
    for dataset in datasets:
        organization = dataset.get("organization") or "Não informado"
        organizations[str(organization)] += 1
        resources = dataset.get("resources") if isinstance(dataset.get("resources"), list) else []
        for resource in resources:
            if isinstance(resource, dict):
                formats[str(resource.get("format") or "Não informado").upper()] += 1
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _e(dataset.get("title") or dataset.get("name") or "Sem título"),
                _e(organization),
                len(resources),
                _e(dataset.get("metadata_modified") or "Não informado"),
            )
        )

    format_rows = "".join(
        '<li><span>{}</span><b>{}</b></li>'.format(_e(label), count)
        for label, count in formats.most_common(8)
    ) or "<li><span>Sem recursos catalogados</span><b>0</b></li>"
    organization_rows = "".join(
        '<li><span>{}</span><b>{}</b></li>'.format(_e(label), count)
        for label, count in organizations.most_common(8)
    ) or "<li><span>Sem órgãos identificados</span><b>0</b></li>"
    table_rows = "".join(rows) or '<tr><td colspan="4" class="empty">Nenhum conjunto disponível. Execute a descoberta CKAN para gerar o catálogo.</td></tr>'

    document = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Relatório reproduzível de metadados do catálogo público do TSE.">
<title>Brasil Eleitoral DataLab · Relatório do Catálogo</title>
<style>
:root{color-scheme:dark;--bg:#07111b;--panel:#0d1c2a;--line:#24445a;--cyan:#60e6ff;--green:#b8ff5c;--muted:#8ba3b4;--text:#e9f5ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 50% 0,#12304a 0,transparent 48%),var(--bg);color:var(--text);font:14px Inter,Arial,sans-serif}
main{max-width:1180px;margin:auto;padding:34px 22px 60px}.eyebrow,.meta,.kpi span,th{font:10px 'Courier New',monospace;letter-spacing:1.4px;color:var(--muted)}
h1{font-size:clamp(30px,5vw,54px);line-height:1;margin:14px 0;color:var(--cyan)}h2{font-size:18px;margin:0 0 16px}
header{border-bottom:1px solid var(--line);padding-bottom:26px}header p{color:var(--muted);line-height:1.6}.status{display:inline-block;border:1px solid #315b45;color:var(--green);padding:7px 10px;font:10px 'Courier New',monospace}
.meta{margin-top:16px;line-height:1.8}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}
.kpi,.panel{background:linear-gradient(145deg,#102235,#09131e);border:1px solid var(--line);padding:18px}
.kpi strong{display:block;color:var(--cyan);font-size:32px;margin-top:9px}.panels{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:12px 0 22px}
ul{list-style:none;margin:0;padding:0}li{display:flex;justify-content:space-between;gap:14px;padding:10px 0;border-bottom:1px solid #1c3445;color:#c4d5df}li b{color:var(--cyan)}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:12px 10px;border-bottom:1px solid #20394b}th{color:var(--cyan)}td{color:#d4e2eb}.empty{color:var(--muted);text-align:center;padding:28px}
.note{border-left:2px solid var(--green);padding:12px 16px;background:#0a1b20;color:#a9c4c8;line-height:1.6;margin-top:18px}
a{color:var(--cyan)}footer{border-top:1px solid var(--line);margin-top:28px;padding-top:18px;color:var(--muted);font:10px 'Courier New',monospace}
@media(max-width:700px){main{padding:22px 14px}.grid{grid-template-columns:1fr}.panels{grid-template-columns:1fr}table{font-size:10px}th,td{padding:9px 6px}}
@media print{body{background:#fff;color:#17212b}main{max-width:none;padding:0}.kpi,.panel{background:#fff;border-color:#ccd6df}.kpi strong,li b,h1,th{color:#075b78}.meta,header p,td,li,footer{color:#394b59}.note{background:#f3f8f5;color:#29463b}a{color:#075b78}}
</style></head>
<body><main>
<header><div class="eyebrow">NR TECH LAB / DATA INTELLIGENCE / 001</div>
<h1>BRASIL ELEITORAL DATALAB</h1>
<div class="status">__STATUS__</div>
<p>Relatório técnico do catálogo público de dados do Tribunal Superior Eleitoral.</p>
<div class="meta">FONTE: <a href="__SOURCE__">Portal de Dados Abertos do TSE</a><br>DESCOBERTA: __GENERATED__<br>RELATÓRIO GERADO: __NOW__</div></header>
<section class="grid">
<article class="kpi"><span>CONJUNTOS CARREGADOS</span><strong>__DATASETS__</strong></article>
<article class="kpi"><span>RECURSOS CATALOGADOS</span><strong>__RESOURCES__</strong></article>
<article class="kpi"><span>ÓRGÃOS IDENTIFICADOS</span><strong>__ORGS__</strong></article>
</section>
<section class="panels"><article class="panel"><h2>Recursos por formato</h2><ul>__FORMATS__</ul></article>
<article class="panel"><h2>Conjuntos por órgão</h2><ul>__ORGANIZATIONS__</ul></article></section>
<section class="panel"><h2>Inventário de conjuntos de dados</h2>
<table><thead><tr><th>CONJUNTO</th><th>ÓRGÃO</th><th>RECURSOS</th><th>ATUALIZAÇÃO</th></tr></thead><tbody>__ROWS__</tbody></table></section>
<div class="note">Escopo e limitação: este documento descreve metadados publicados no catálogo CKAN. Não apresenta votos, candidaturas, comparecimento, abstenção ou resultados eleitorais. Indicadores eleitorais exigem ingestão e validação dos arquivos oficiais correspondentes.</div>
<footer>NR TECH LAB · BRASIL ELEITORAL DATALAB · RELATÓRIO HTML AUTÔNOMO</footer>
</main></body></html>"""

    replacements = {
        "__STATUS__": _e(status),
        "__SOURCE__": _e(source),
        "__GENERATED__": _e(generated_at),
        "__NOW__": _e(datetime.now(timezone.utc).isoformat(timespec="seconds")),
        "__DATASETS__": str(len(datasets)),
        "__RESOURCES__": str(sum(len(d.get("resources", [])) for d in datasets if isinstance(d.get("resources"), list))),
        "__ORGS__": str(len(organizations)),
        "__FORMATS__": format_rows,
        "__ORGANIZATIONS__": organization_rows,
        "__ROWS__": table_rows,
    }
    for token, value in replacements.items():
        document = document.replace(token, value)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("catalog/tse/datasets/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/catalog/index.html"))
    args = parser.parse_args()
    result = build_report(args.manifest, args.output)
    print(f"HTML report generated: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
