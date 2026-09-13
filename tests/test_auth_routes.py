import unittest
from unittest.mock import Mock, patch

import jwt

from app import app
from auths.routes import SECRET_KEY


class AuthRoutesTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    @patch("auths.routes.criptografar_senha", return_value="senha-hash")
    @patch("auths.routes.FIRST_USER_ADMIN", True)
    @patch("auths.routes.conectar")
    def test_primeiro_usuario_local_pode_ser_admin(self, conectar, _criptografar):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.side_effect = [None, (True,)]
        conn.cursor.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.post(
            "/cadastro",
            json={
                "nome": "Administrador Local",
                "email": "admin@example.com",
                "senha": "senha-segura",
            },
        )

        self.assertEqual(resposta.status_code, 201)
        self.assertEqual(resposta.json, {"mensagem": "usuario criado com sucesso"})
        comando_insert = cursor.execute.call_args_list[-1]
        self.assertTrue(comando_insert.args[1][-1])
        conn.commit.assert_called_once()

    @patch("auths.routes.criptografar_senha", return_value="senha-hash")
    @patch("auths.routes.FIRST_USER_ADMIN", False)
    @patch("auths.routes.ADMIN_EMAILS", {"dono@example.com"})
    @patch("auths.routes.conectar")
    def test_email_configurado_recebe_admin_em_producao(self, conectar, _criptografar):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = None
        conn.cursor.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.post(
            "/cadastro",
            json={
                "nome": "Dono",
                "email": "Dono@Example.com",
                "senha": "senha-segura",
            },
        )

        self.assertEqual(resposta.status_code, 201)
        comando_insert = cursor.execute.call_args_list[-1]
        self.assertEqual(comando_insert.args[1][2], "dono@example.com")
        self.assertTrue(comando_insert.args[1][-1])

    @patch("auths.routes.conectar")
    def test_login_com_nome_cria_ou_recupera_usuario(self, conectar):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = (7, "Eduardo", False)
        conn.cursor.return_value = cursor
        conectar.return_value = conn

        primeira = self.client.post("/login", json={"nome": " Eduardo "})
        segunda = self.client.post("/login", json={"nome": "EDUARDO"})

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primeira.json["usuario"], {"id": 7, "nome": "Eduardo"})
        self.assertEqual(segunda.json["usuario"]["id"], 7)
        self.assertIn("token", primeira.json)
        self.assertTrue(
            all(
                "ON CONFLICT (nome_normalizado)" in chamada.args[0]
                for chamada in cursor.execute.call_args_list
            )
        )
        self.assertEqual(cursor.execute.call_args_list[0].args[1], ("Eduardo", "eduardo"))
        self.assertEqual(cursor.execute.call_args_list[1].args[1], ("EDUARDO", "eduardo"))

    @patch("auths.routes.conectar")
    def test_login_normaliza_espacos_e_jwt_possui_sub_estavel(self, conectar):
        conn = Mock()
        cursor = Mock()
        cursor.fetchone.return_value = (11, "Maria Silva", False)
        conn.cursor.return_value = cursor
        conectar.return_value = conn

        resposta = self.client.post("/login", json={"nome": "  Maria   Silva  "})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(cursor.execute.call_args.args[1], ("Maria Silva", "maria silva"))
        payload = jwt.decode(
            resposta.json["token"], SECRET_KEY, algorithms=["HS256"]
        )
        self.assertEqual(payload["sub"], "11")
        self.assertEqual(payload["id"], 11)

    def test_login_rejeita_nome_vazio_curto_ou_longo(self):
        for nome in ("", " ", "A", "x" * 101):
            with self.subTest(nome=nome):
                resposta = self.client.post("/login", json={"nome": nome})
                self.assertEqual(resposta.status_code, 400)
                self.assertEqual(resposta.json, {"erro": "nome invalido"})

    def test_login_rejeita_payload_sem_nome(self):
        resposta = self.client.post("/login", json={"email": "antigo@example.com"})

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json, {"erro": "nome invalido"})


if __name__ == "__main__":
    unittest.main()
