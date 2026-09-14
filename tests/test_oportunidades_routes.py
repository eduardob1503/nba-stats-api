import os
import unittest
from datetime import date
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("SECRET_KEY", "segredo-de-teste-com-mais-de-32-bytes")

import jwt

from app import app


def _token():
    return jwt.encode({"sub": "7"}, os.environ["SECRET_KEY"], algorithm="HS256")


BASE = (
    "/oportunidades/ev?temporada=2025-26&tipo_temporada=Regular%20Season"
    "&mercado=cestas_3&linha=1.5&odd=1.90&lado=over"
    "&quantidade_jogos=10&minimo_jogos=1&limite=20"
)


class OportunidadesRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {_token()}"}

    def test_exige_autenticacao(self):
        resposta = self.client.get(BASE)

        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta.json, {"erro": "token invalido ou expirado"})

    def test_rejeita_parametros_invalidos_com_422(self):
        casos = {
            "mercado=gols": "mercado invalido",
            "temporada=2024-25": "temporada invalida",
            "tipo_temporada=Pre%20Season": "tipo de temporada invalido",
            "quantidade_jogos=3": "quantidade de jogos invalida",
            "minimo_jogos=0": "minimo de jogos invalido",
            "minimo_jogos=11": "minimo de jogos invalido",
            "limite=0": "limite invalido",
            "limite=101": "limite invalido",
            "linha=-1": "linha invalida",
            "linha=abc": "linha invalida",
            "odd=1": "odd invalida",
            "odd=abc": "odd invalida",
            "lado=acima": "lado invalido",
            "linhas_plausiveis=sim": "linhas plausiveis invalido",
            "percentil_inferior=-1": "percentil inferior invalido",
            "percentil_inferior=abc": "percentil inferior invalido",
            "percentil_inferior=51": "percentil inferior invalido",
            "percentil_superior=49": "percentil superior invalido",
            "percentil_superior=101": "percentil superior invalido",
            "percentil_superior=abc": "percentil superior invalido",
            "edge_minimo_percentual=-1": "edge minimo invalido",
            "edge_minimo_percentual=abc": "edge minimo invalido",
            "edge_maximo_percentual=-1": "edge maximo invalido",
            "edge_maximo_percentual=101": "edge maximo invalido",
            "edge_maximo_percentual=abc": "edge maximo invalido",
        }
        for substituicao, mensagem in casos.items():
            campo = substituicao.split("=", 1)[0]
            caminho, _, query = BASE.partition("?")
            partes = [
                parte for parte in query.split("&")
                if not parte.startswith(f"{campo}=")
            ]
            url = f"{caminho}?{'&'.join([*partes, substituicao])}"
            with self.subTest(parametro=substituicao):
                resposta = self.client.get(url, headers=self.headers)
                self.assertEqual(resposta.status_code, 422)
                self.assertEqual(resposta.json["erro"], mensagem)

    def test_rejeita_faixas_de_percentil_e_edge_invalidas(self):
        casos = (
            ("&percentil_inferior=50&percentil_superior=50", "faixa de percentis invalida"),
            ("&percentil_inferior=40&percentil_superior=30", "faixa de percentis invalida"),
            ("&edge_minimo_percentual=20&edge_maximo_percentual=20", "faixa de edge invalida"),
            ("&edge_minimo_percentual=21&edge_maximo_percentual=20", "faixa de edge invalida"),
        )
        for parametros, mensagem in casos:
            with self.subTest(parametros=parametros):
                resposta = self.client.get(BASE + parametros, headers=self.headers)
                self.assertEqual(resposta.status_code, 422)
                self.assertEqual(resposta.json["erro"], mensagem)

    @patch("services.nba.playergamelog.PlayerGameLog")
    @patch("oportunidades.routes.conectar")
    def test_consulta_unica_sem_nba_api_e_retorna_contrato(self, conectar, nba_api):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            (30, "Stephen Curry", "g2", date(2026, 1, 2), 30, 7, 5, 4, 10),
            (30, "Stephen Curry", "g1", date(2026, 1, 1), 25, 6, 4, 2, 8),
        ]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get(BASE, headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(cursor.execute.call_count, 1)
        self.assertIn("ROW_NUMBER() OVER", cursor.execute.call_args.args[0])
        self.assertEqual(cursor.execute.call_args.args[1], ["2025-26", "Regular Season", 10])
        nba_api.assert_not_called()
        self.assertEqual(resposta.json["total_jogadores_avaliados"], 1)
        self.assertEqual(resposta.json["total_elegiveis"], 1)
        self.assertFalse(resposta.json["filtros"]["linhas_plausiveis"])
        self.assertEqual(resposta.json["filtros"]["percentil_inferior"], 25)
        self.assertEqual(resposta.json["filtros"]["percentil_superior"], 75)
        self.assertEqual(resposta.json["filtros"]["edge_minimo_percentual"], 3)
        self.assertEqual(resposta.json["filtros"]["edge_maximo_percentual"], 20)
        self.assertEqual(resposta.json["total_ev_positivo_bruto"], 1)
        self.assertEqual(resposta.json["total_linhas_plausiveis"], 1)
        self.assertEqual(resposta.json["total_retornado"], 1)
        item = resposta.json["oportunidades"][0]
        self.assertEqual(item["jogador"], {
            "id": "nba:30",
            "nba_player_id": 30,
            "nome": "Stephen Curry",
            "ativo": None,
        })
        self.assertEqual(item["jogos_selecionados"], 2)
        self.assertEqual(item["ultimo_valor"], 4)

    @patch("oportunidades.routes.conectar")
    def test_parsing_explicito_true_e_false(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            (30, "Stephen Curry", "g2", date(2026, 1, 2), 30, 7, 5, 4, 10),
            (30, "Stephen Curry", "g1", date(2026, 1, 1), 25, 6, 4, 2, 8),
        ]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn
        url_true = (
            BASE.replace("linha=1.5", "linha=2.5")
            .replace("odd=1.90", "odd=2.1")
            + "&linhas_plausiveis=true&edge_minimo_percentual=0"
        )

        resposta_true = self.client.get(url_true, headers=self.headers)
        resposta_false = self.client.get(
            BASE + "&linhas_plausiveis=false", headers=self.headers
        )

        self.assertEqual(resposta_true.status_code, 200)
        self.assertTrue(resposta_true.json["filtros"]["linhas_plausiveis"])
        self.assertEqual(resposta_true.json["total_ev_positivo"], 1)
        self.assertTrue(resposta_true.json["oportunidades"][0]["linha_dentro_faixa"])
        self.assertTrue(resposta_false.json["filtros"]["linhas_plausiveis"] is False)

    @patch("oportunidades.routes.conectar")
    def test_tipo_todos_quantidade_todos_e_defaults(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, "Jogador", "g1", date(2026, 1, 1), 20, 5, 5, 2, 5)
        ] * 5
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn
        url = (
            "/oportunidades/ev?temporada=2025-26&mercado=pontos&linha=10"
            "&odd=1.9&lado=over&quantidade_jogos=todos"
        )

        resposta = self.client.get(url, headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["filtros"]["tipo_temporada"], "Todos")
        self.assertEqual(resposta.json["filtros"]["minimo_jogos"], 5)
        self.assertEqual(resposta.json["filtros"]["limite"], 20)
        sql, parametros = cursor.execute.call_args.args
        self.assertNotIn("ordem_recente <=", sql)
        self.assertEqual(parametros, ["2025-26"])

    @patch("oportunidades.routes.conectar")
    def test_temporada_sem_partidas_retorna_404_amigavel(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = []
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get(BASE, headers=self.headers)

        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(resposta.json, {
            "erro": "temporada ainda nao sincronizada",
            "temporada": "2025-26",
        })

    @patch("oportunidades.routes.conectar")
    def test_sem_ev_positivo_retorna_200_com_lista_vazia(self, conectar):
        conn = MagicMock()
        cursor = Mock()
        cursor.fetchall.return_value = [
            (1, "Jogador", "g1", date(2026, 1, 1), 20, 5, 5, 0, 3)
        ]
        conn.cursor.return_value.__enter__.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.get(BASE + "&linhas_plausiveis=true", headers=self.headers)

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json["total_ev_positivo"], 0)
        self.assertEqual(resposta.json["oportunidades"], [])


if __name__ == "__main__":
    unittest.main()
