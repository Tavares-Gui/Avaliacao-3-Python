"""Gera um .env local com chave aleatória, sem sobrescrever configurações."""
from pathlib import Path
import secrets

base = Path(__file__).resolve().parent.parent
destino = base / ".env"
if destino.exists():
    print(".env já existe; nenhuma configuração foi alterada.")
else:
    conteudo = (base / ".env.example").read_text(encoding="utf-8")
    conteudo = conteudo.replace("troque-por-uma-chave-gerada-localmente", secrets.token_urlsafe(64))
    destino.write_text(conteudo, encoding="utf-8")
    print(".env criado com SECRET_KEY aleatória. Não envie esse arquivo ao GitHub.")
