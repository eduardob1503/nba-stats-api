import unittest
from unittest.mock import Mock, patch

from app import app


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


if __name__ == "__main__":
    unittest.main()
