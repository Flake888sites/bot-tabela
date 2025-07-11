import os
import json
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta

TOKEN = os.getenv("DISCORD_TOKEN")  # variável de ambiente no Render
HISTORICO_FILE = "pedidos.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

VENDEDORES_IDS = [1387197480994603190, 1334348969987411978]

BASE_COOLDOWNS = {
    "1 vídeo": timedelta(minutes=10),
    "3 vídeos": timedelta(minutes=20),
    "5 vídeos": timedelta(minutes=30),
}

if os.path.exists(HISTORICO_FILE):
    with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
        historico_pedidos = json.load(f)
else:
    historico_pedidos = []

cooldowns = {}

def salvar_historico():
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(historico_pedidos, f, ensure_ascii=False, indent=4)

def pode_pedir(user_id, pacote):
    if user_id in VENDEDORES_IDS:
        return True, None

    agora = datetime.utcnow()
    user_cd = cooldowns.get(user_id, {})
    pacote_cd = user_cd.get(pacote, None)

    base_cooldown = BASE_COOLDOWNS[pacote]

    if pacote_cd is None:
        return True, None

    last_order = pacote_cd["last_order"]
    current_cd = pacote_cd["current_cooldown"]

    if agora >= last_order + current_cd:
        return True, None
    else:
        restante = (last_order + current_cd) - agora
        return False, restante

def atualizar_cooldown(user_id, pacote):
    agora = datetime.utcnow()
    user_cd = cooldowns.setdefault(user_id, {})
    pacote_cd = user_cd.get(pacote)

    base_cooldown = BASE_COOLDOWNS[pacote]

    if pacote_cd is None:
        user_cd[pacote] = {
            "last_order": agora,
            "current_cooldown": base_cooldown
        }
    else:
        novo_cd = pacote_cd["current_cooldown"] + base_cooldown
        user_cd[pacote] = {
            "last_order": agora,
            "current_cooldown": novo_cd
        }

@tasks.loop(minutes=60)
async def resetar_cooldowns():
    agora = datetime.utcnow()
    for user_id in list(cooldowns.keys()):
        user_cd = cooldowns[user_id]
        for pacote in list(user_cd.keys()):
            last_order = user_cd[pacote]["last_order"]
            if agora >= last_order + timedelta(hours=24):
                user_cd[pacote]["current_cooldown"] = BASE_COOLDOWNS[pacote]

@tasks.loop(minutes=60)
async def limpar_historico():
    agora = datetime.utcnow()
    inicial_len = len(historico_pedidos)
    historico_pedidos[:] = [
        pedido for pedido in historico_pedidos
        if datetime.fromisoformat(pedido["hora"]) > agora - timedelta(days=2)
    ]
    if len(historico_pedidos) != inicial_len:
        salvar_historico()

@bot.event
async def on_ready():
    print(f"🤖 Bot online como {bot.user}")
    resetar_cooldowns.start()
    limpar_historico.start()

@bot.command()
async def tabela(ctx):
    if ctx.author.id not in VENDEDORES_IDS:
        await ctx.send("🚫 Você não tem permissão para usar este comando.")
        return

    button = Button(label="Ver tabela de preços", style=discord.ButtonStyle.primary)

    async def button_callback(interaction):
        view_pacotes = View()

        pacotes = [
            ("Comprar 1 vídeo - R$20", "1 vídeo"),
            ("Comprar 3 vídeos - R$50", "3 vídeos"),
            ("Comprar 5 vídeos - R$80", "5 vídeos"),
        ]

        for label, pacote_nome in pacotes:
            pacote_button = Button(label=label, style=discord.ButtonStyle.success)

            async def pedido_callback(inner_interaction, pacote=pacote_nome):
                user_id = inner_interaction.user.id
                pode, restante = pode_pedir(user_id, pacote)
                if not pode:
                    minutos = int(restante.total_seconds() // 60) + 1
                    await inner_interaction.response.send_message(
                        f"⏳ Você deve esperar {minutos} minuto(s) para pedir este pacote novamente.",
                        ephemeral=True
                    )
                    return

                atualizar_cooldown(user_id, pacote)

                if user_id not in VENDEDORES_IDS:
                    pedido = {
                        "usuario_id": user_id,
                        "usuario_nome": inner_interaction.user.name,
                        "pacote": pacote,
                        "hora": datetime.utcnow().isoformat()
                    }
                    historico_pedidos.append(pedido)
                    salvar_historico()

                for vendedor_id in VENDEDORES_IDS:
                    vendedor = bot.get_user(vendedor_id)
                    if vendedor:
                        try:
                            await vendedor.send(f"📢 O membro **{inner_interaction.user}** pediu o pacote: **{pacote}**")
                        except Exception as e:
                            print(f"Erro ao enviar DM para {vendedor_id}: {e}")

                await inner_interaction.response.defer(ephemeral=True)
                await inner_interaction.followup.send(
                    f"✅ Pedido do pacote **{pacote}** enviado para os vendedores!",
                    ephemeral=True
                )

            pacote_button.callback = pedido_callback
            view_pacotes.add_item(pacote_button)

        tabela_msg = (
            "**🎬 Tabela de Preços das Animações**\\n\\n"
            "- 1 vídeo: R$20\\n"
            "- 3 vídeos: R$50\\n"
            "- 5 vídeos: R$80\\n\\n"
            "Escolha um dos pacotes abaixo:"
        )

        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(tabela_msg, view=view_pacotes, ephemeral=True)

    button.callback = button_callback
    view = View()
    view.add_item(button)

    await ctx.send("Clique no botão abaixo para ver os preços:", view=view)

@bot.command()
async def pedidos(ctx):
    try:
        print(f"[DEBUG] !pedidos chamado por {ctx.author} ({ctx.author.id})")

        if ctx.author.id not in VENDEDORES_IDS:
            await ctx.send("🚫 Você não tem permissão para ver os pedidos.")
            print("[DEBUG] Acesso negado")
            return

        if not historico_pedidos:
            await ctx.send("📦 Nenhum pedido feito ainda.")
            print("[DEBUG] Histórico vazio")
            return

        mensagem = "**📜 Histórico de Pedidos:**\\n\\n"
        for pedido in historico_pedidos:
            usuario = pedido.get("usuario_nome", "Desconhecido")
            pacote = pedido.get("pacote", "???")
            hora = pedido.get("hora", "???")
            mensagem += f"👤 {usuario} — {pacote} — {hora[:16]}\\n"

        await ctx.send(mensagem)
        print("[DEBUG] Mensagem enviada com sucesso")

    except Exception as e:
        print(f"[ERRO] no comando !pedidos: {e}")
        await ctx.send("❌ Ocorreu um erro ao mostrar os pedidos.")


bot.run(TOKEN)

