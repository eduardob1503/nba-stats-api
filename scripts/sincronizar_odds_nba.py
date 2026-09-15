import argparse
import sys

from services.oddspapi import OddsPapiClient, OddsPapiError
from services.odds_normalizacao import MERCADOS_REAIS
from services.odds_sync import OddsSyncError, sincronizar_odds


def _argumentos(argv=None):
    parser = argparse.ArgumentParser(
        description="Sincroniza props reais da NBA sem expor a chave da OddsPapi."
    )
    parser.add_argument("--bookmaker", default="betano")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-eventos", type=int)
    parser.add_argument(
        "--mercados",
        help="Lista separada por virgulas: " + ",".join(MERCADOS_REAIS),
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = _argumentos(argv)
    if args.max_eventos is not None and args.max_eventos < 1:
        print("--max-eventos deve ser maior que zero", file=sys.stderr)
        return 2
    mercados = None
    if args.mercados:
        mercados = {
            item.strip().lower()
            for item in args.mercados.split(",")
            if item.strip()
        }

    try:
        resumo = sincronizar_odds(
            OddsPapiClient(),
            bookmaker=args.bookmaker,
            dry_run=args.dry_run,
            max_eventos=args.max_eventos,
            mercados=mercados,
            output=print,
        )
    except (OddsPapiError, OddsSyncError) as erro:
        print(f"Falha segura ({erro.codigo}): {erro}", file=sys.stderr)
        return 1
    except Exception:
        print("Falha interna durante a sincronizacao de odds", file=sys.stderr)
        return 1

    modo = "dry-run" if args.dry_run else "sincronizacao"
    print(
        f"{modo} concluido: {resumo['eventos_consultados']} eventos, "
        f"{resumo['props_salvas']} props salvas, "
        f"{resumo['requisicoes_utilizadas']} requisicoes utilizadas."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
