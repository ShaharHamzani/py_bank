from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date, time
from functools import wraps, reduce
from enum import StrEnum
import inspect
import asyncio
import random


# Accounts (Transactions) Iterator:
class TransactionIterator():
    """A transaction Iterator class for iteration over the list of transactions
    Args: 
        transactions_list (list[Transaction]) The list of transactions
        filter (str) A filter used for filering the list to only one type (e.g "Deposit")
    Attributes:
        _index (int) Index used for indexing the list while iteration
    """
    def __init__(self, transactions_list, filter=None):
        self.transactions_list = [t for t in transactions_list if filter is None or t.type == filter.upper()]
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self.transactions_list):
            raise StopIteration
        item = self.transactions_list[self._index]
        self._index += 1
        return item


# Account Class:
class Account(ABC):
    """An abstract class representing a personal bank accountt
    
    Arguments:
        owner (str) The account owner's name.
        account_number (str) The account number that identifys it. (can also be called identification number.)
        inital_balance (float) The balance the account will start with.
    Attributes:
        _balance (float) Acount balance tracker.
        _transactions (list[Transaction]) Transactions recorded for this account.
    """

    def __init__(self, owner: str, account_number: str, initial_balance: float = 0.0):
        if initial_balance < 0:
            raise ValueError("Balance cannot be negative.")
        self.owner = owner
        self.account_number = account_number
        self._balance = initial_balance
        self._transactions = [] # lis of type Transactions to save all transactions

    def __repr__(self):
        return f"Account(owner='{self.owner}', account_number='{self.account_number}', balance={self._balance})"
    
    def __str__(self):
        return f"{self.owner}'s Account | Balance: ${self._balance}."

    def __eq__(self, other):
        """Returns true if the ACCOUNT NUMBERS are equal."""
        return self.account_number == other.account_number

    def __hash__(self):
        """Hashes only the account number of the account."""
        return hash(self.account_number)

    def __len__(self):
        """Returns the number of transactions"""
        return len(self._transactions)

    def __getitem__(self, index):
        """Supports account[0], account[-1], and slicing like account[0:3]."""
        return self._transactions[index]

    def __iter__(self):
        """Supports iteration on the trasactions list."""
        return TransactionIterator(self._transactions)

    def __contains__(self, transaction) -> bool:
        """Supports 'transaction in account'."""
        return transaction in self._transactions

    def iter_with_filter(self, filter=None):
        """Supports iteration on the trasactions list with filter."""
        return TransactionIterator(self._transactions, filter)

    @abstractmethod
    def deposit(self, amount, is_interest=False):
        """Deposits funds according to account-specific rules. Creates a record of the transaction(deposit/interest) too.
        Args:
            amount (float) the amout to deposit
            is_interest (bool) show if the deosit came from interest or not.
        """
        if not is_interest:   
            self.record_transaction(TransactionTypes.DEPOSIT, amount)
        else:
            self.record_transaction(TransactionTypes.INTEREST, amount)

    @abstractmethod
    def withdraw(self, amount):
        """Withdraws funds according to account-specific rules. Creates a record of the transaction too.
        Args:
            amount (float) the amout to withdraw""" 
        self.record_transaction(TransactionTypes.WITHDRAWAL, amount)

    @property
    def balance(self):
        """A property that returns the acount balance."""
        return self._balance
    
    def record_transaction(self, type: str, amount:float):
        """Appends a transaction to the transations list
        Args:
            type (str) The type of transaction (e.g DEPOSIT)
            amount (float) The amount of transaction   
        """
        amount = abs(amount) # abs the amount so no negative value enters
        self._transactions.append(Transaction(type, amount))


# Accounts Decorators:
def audit(func):
    """Simply logs every Deposit/Withdeaw/Interest"""
    sig = inspect.signature(func)
    @wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        is_interest = list(bound_args.arguments.items())[2][1]

        type = ""
        if func.__name__ == "withdraw":
            type = TransactionTypes.WITHDRAWAL
        elif func.__name__ == "deposit" and is_interest:
            type = TransactionTypes.INTEREST
        else: # func.__name__ == "deposit":
            type = TransactionTypes.DEPOSIT

        Bank.logger.log(f"[{datetime.now()}] CALLED {type} on {str(args[0]).split(" Account")[0]}{args[0].__class__.__name__} | args: ({args[1]})")
        return func(*args, **kwargs)
    return wrapper


def validat_amount(min_amount=0.01):
    """A decorator factory that makes sure the value enered is valid. (for deposit methods.)"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if args[1] < min_amount:
                raise ValueError(f"Value must be {min_amount} amount or above")
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Accounts Generators:
def compound_interest(principal, rate, periods):
    """Yields the new balance after each periods untile the amount of periods entered.

    Args:
        principal (float) the amount of money before the start of savings.
        rate (float) The fractional growth multiplier per step, expressed as a decimal
        periods (int) The amount of periods to return the multiplication.
    """
    for period in range(1, periods+1):
        balance = principal * (1 + rate) ** period
        yield balance


def monthly_statements(account):
    """Yields a formatted string summary for each transaction in the account, arranged monthly.
    
    Args:
        account (Account) the account the summary is about.
    """
    month = 0 # initialize zero as dummy value for start
    for transaction in account:
        if transaction.timestep.month == month:
            yield str(transaction)
        else:
            month = transaction.timestep.month
            yield f"---{transaction.timestep.year}:{transaction.timestep.month}---\n{str(transaction)}"


def filter_transactions(account, transaction_type, min_amount):
    "Returns a generator that outputs only the appropriate transactions."
    return (transaction for transaction in account if transaction.type.upper() == transaction_type and transaction.amount >= min_amount)


# Account Heirs:
class SavingsAccount(Account):
    """Savings account with interest rate.
    Additional Args:
        _interest_rate (float) The fractional growth multiplier per step, expressed as a decimal.
    """

    def __init__(self, owner: str, account_number: str, initial_balance: float = 0.0,  interest_rate: float = 0.01):
        if interest_rate < 1 and interest_rate > 0:
            super().__init__(owner, account_number, initial_balance)
            self._interest_rate = interest_rate

    @property
    def account_type(self):
        """Returns the account type."""
        return f"Savings"
    
    @property
    def interest_rate(self):
        """Returns the intrest rate"""
        return self._interest_rate

    @audit
    @validat_amount()
    def deposit(self, amount, is_interest=False):
        """Deposits funds if the deposit value is positive, otherwise raises ValueError.
        Args:
            amount (float) the amout to deposit
            is_interest (bool) show if the deosit came from interest or not.
            """
        self._balance += amount
        super().deposit(amount, is_interest)
    
    @audit
    def withdraw(self, amount, is_interest=False):
        """Withdraws funds if the balance after the action will not be negative.
        (The function handles the case where the withdraw amount is negative and works the same way.)
        Args:
            amount (float) the amout to withdraw
            is_interest (bool) !Not needed in this funcion, here only for syntax reasons!
        """ 

        if abs(amount) > self._balance:
            raise ValueError("Balance value cant stay negative.")
        elif amount == 0:
            raise ValueError("Cannot withdraw with value of zero.")
        self._balance -= abs(amount)
        super().withdraw(amount)

    def apply_interest(self, periods):
        """Deposits the intrest added value based on the number of periods to the account balance and lets it know it was an interest deposit and not a normal one.
        Args:
            periods (int) The amount of periods of savings.
        """
        gen = compound_interest(self.balance, self.interest_rate, periods)
        new_balance = reduce(lambda _, x: x, gen)
        self.deposit(new_balance - self.balance, True) # True means interest deposit


class LoanAccount(Account):
    """Savings account with interest rate.
        Additional Args:
            credit_limit (float) The max limit of possible loan.
    """

    def __init__(self, owner: str, account_number: str, credit_limit: float):
        super().__init__(owner, account_number, 0)
        self.credit_limit = credit_limit

    def __str__(self):
        return f"{self.owner}'s Account | Debt: ${self._balance}."

    @property
    def account_type(self):
        """Returns the account type."""
        return "Loan"

    @audit
    @validat_amount()
    def deposit(self, amount, is_interest=False):
        """Deposits funds (Closes the debt) if the deposit value is positive, and it won't overflow otherwise raises ValueError
        Args:
            amount (float) the amout to deposit
            is_interest (bool) !Not needed in this funcion, here only for syntax reasons! (show if the deosit came from interest or not.)
        """
        
        if self._balance + amount > 0:
            raise ValueError("You can close the dept. Deposit only the necesarry amount.")
        self._balance += amount
        super().deposit(amount)
    
    @audit 
    def withdraw(self, amount, is_interest=False):
        """Withdraws funds (Increases the debt) if the balance after the action will not exeed the credit limit.
        (The function handles the case where the withdraw amount is negative and works the same way.)
        Args:
            amount (float) the amout to withdraw 
            is_interest (bool) !Not needed in this funcion, here only for syntax reasons!
        """ 

        if self._balance - abs(amount) < -self.credit_limit:
            raise ValueError("Exeeded credit limit.")
        elif amount == 0:
            raise ValueError("Cannot withdraw with value of zero.")
        self._balance -= abs(amount)
        super().withdraw(amount)


# Factory of accounts:
class AccountFactory:
    """Factory class responsible for creating Bank Account objects, and generating identifier account number for each account"""

    @staticmethod
    def _acc_num_gen():
        """Yields account numbers as strings.

        Yields:
            str: Next sequential integer account identifier.
        """
        n = 1
        while True:
            yield str(n)
            n += 1

    @staticmethod
    def _generate_next_id(gen=_acc_num_gen()):
        """Retrieves the next unique account ID from the account numbers generator.
        In Python, default argument values ​​in a function are evaluated only once. Which causes the generator to initialize only once, And thanks to this, numbers are emitted correctly.
        """
        return next(gen)
    
    @staticmethod
    def create_account(owner: str, acc_type: str, additional_info: float, initial_balance=0.0):
        """Factory method for creating a new account and generating an identifier account number for it.
        
        Args:
            owner (str) The account owner's name.
            acc_type (str) The type of the account. (e.g Savings/Loan)
            additional_info (float) an argument saves the data for one of these options based on the account type:
                credit_limit (float) The max limit of possible loan.
                interest_rate (float) The fractional growth multiplier per step, expressed as a decimal.
            inital_balance (float) The balance the account will start with. (optional.)
        """

        acc_type = acc_type.lower()

        if acc_type == "savings":
            account_number = AccountFactory._generate_next_id()
            return SavingsAccount(owner, account_number, initial_balance, additional_info)
        elif acc_type == "loan":
            account_number = AccountFactory._generate_next_id()
            return LoanAccount(owner, account_number, additional_info)
        elif acc_type == "loan" and initial_balance != 0:
            raise ValueError("Loan account cannot initialize with value.")
        else:
            raise ValueError("Unlnown account type")


# Transaction Data Class:
@dataclass(frozen=True) 
class Transaction:
    """Represents a financial transaction in an account.
    
        Attributes:
            type (str) The category of the transaction.
            amount (float) The value of the transaction in .
            timestep (datetime) The exact time of the transaction.
    """
    type: str # e.g: DEPOSIT
    amount: float
    timestep: datetime = field(default_factory=datetime.now, init=False)

    def __str__(self):
        return f"[{self.timestep}] {self.type} | ${self.amount}"


# Transaction Types Enum:
class TransactionTypes(StrEnum):
    """An Enum holds the possible transaction types"""
    WITHDRAWAL = "WITHDRAWAL"
    DEPOSIT = "DEPOSIT"
    INTEREST = "INTEREST"


# An additional AuditLog class dedicated to Bank:
class AuditLog:
    """Singleton audit log for recording actions.

    Attributes:
        _logs (list[str]): Recorded log messages
    """
    _instance = None # Singleton pattern: only one Bank instance is created

    def __new__(cls):
        """Returns the singleton AuditLog instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._logs = []
        self._initialized = True

    def __iter__(self):
        """Creates and returns an iterable of logs list"""
        return iter(self._logs)

    def __len__(self):
        """Returns the length of the logs list"""
        return len(self._logs)

    def log(self, message):
        """Adds a log to the logs list"""
        self._logs.append(message)

    def clear(self):
        """Clears the logs list"""
        self._logs.clear()


# Bank Class (Hes accounts):
class Bank():
    """Singleton Bank class only one instance is ever be created.
    
    Args:
        name (str) The bank's name
    Attributes:
        _accounts (dictionary) A dictionary of the bank accounts account_number:account
        logger (AuditLog) An instance of AuditLog logger
    """
    _instance = None # Singleton pattern: only one Bank instance is created
    logger = AuditLog()

    def __new__(cls, name: str):
        """Returns the singleton Bank instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance


    def __init__(self, name):
        """Creates ones the variables for the only instace of the bank"""
        if self._initialized:
            return
        
        self.name = name
        self._accounts = {}
        self._initialized = True

    def __len__(self):
        """Returns accounts number"""
        return len(self._accounts)

    def __getitem__(self, account_number):
        """Returns the account based of the account number given."""
        return self._accounts[account_number]

    def __contains__(self, item) -> bool:
        """Supports 'account_number in bank'."""
        return item in self._accounts

    def __str__(self):
        return f"{self.name} | Accounts: {len(self._accounts)}"

    @property
    def accounts(self):
        """A property that returns the list of acounts."""
        return list(self._accounts.values())

    def create_account(self, owner: str, acc_type: str, additional_info: float, initial_balance=0.0):
        """Creates and adds new account to the bank.
        
        Args:
            owner (str) The account owner's name.
            acc_type (str) The type of the account. (e.g Savings/Loan)
            additional_info (float) an argument saves the data for one of these options based on the account type:
                credit_limit (float) The max limit of possible loan.
                interest_rate (float) The fractional growth multiplier per step, expressed as a decimal.
            inital_balance (float) The balance the account will start with. (optional.)
        """
        try:
            new_acc = AccountFactory.create_account(owner, acc_type, additional_info, initial_balance)
        except ValueError as e:
            return f"Account creation failed: {e}"
        else:
            self._accounts[new_acc.account_number] = new_acc
            return new_acc

    def remove_account(self, account_number):
        """Removes the account from the bank.
        
        Args:
            account_number (str) The number of the account used to find the account and delete from the dict.
        """
        if account_number not in self._accounts:
            raise ValueError("Account number not found.")
        deletion_account = self._accounts[account_number]
        del self._accounts[account_number]
        del deletion_account

    def get_account(self, account_number):
        """Returns the account asked.
                
        Args:
            account_number (str) The number of the account used to find the account in the dict.
        """
        if account_number not in self._accounts:
            raise ValueError("Account number not found.")
        return self._accounts[account_number]

    def transfer(self, from_number, to_number, amount):
        """Transfers the money enterd between two accounts
                        
        Args:
            from_number (str) The number of the paying account.
            to_number (str) The number of the reciving account.
            amount (float) the amount of money to transfer
        """
        if from_number not in self._accounts:
            raise ValueError("Payer account number not found.")
        elif to_number not in self._accounts:
            raise ValueError("Reciver account number not found.")
        
        self._accounts[from_number].withdraw(amount)
        self._accounts[to_number].deposit(amount)


# Async Functions dedicated to Bank:
async def async_transfer(bank, from_number, to_number, amount):
    """Asynchronously transfers funds between two account numbers. Uses AccountLock to lock the accounts while transfer.

    Args:
        bank (Bank) The bank of the accounts
        from_number (str) The number of the paying account.
        to_number (str) The number of the reciving account.
        amount (float) the amount of money to transfer

    (Returns a ValueError if needed.)
    """

    delay = random.uniform(0.1, 0.5) # Represents network delay
    await asyncio.sleep(delay)

    async with AccountLock(from_number): # Lock the payer account
        async with AccountLock(to_number):  # Lock the receiver account
            try:
                bank.transfer(from_number, to_number, amount)
            except Exception as e:
                return f"Transfer failed: {e}"
            else:
                return f"Transfer of ${amount:.2f} from {from_number} to {to_number} — OK 200"


async def async_batch_transfer(bank, transfers):
    """Concurrently processes a batch of bank transfers.

    Executes multiple bank transfer operations simultaneously using an asynchronous
    event loop and collects their completion results.
    
    Args:
        bank (Bank) The bank of the accounts
        transfers (list) transfers: A list of tuples, where each tuple contains:
            from_number (str) The number of the paying account.
            to_number (str) The number of the reciving account.
            amount (float) the amount of money to transfer

    Returns:
        List[str]: A list of result messages corresponding to each transfer in order,
        indicating whether each transfer succeeded ("— OK") or failed ("Transfer failed: ...").
    """

    tasks = [
        async_transfer(bank, from_num, to_num, amount)
        for from_num, to_num, amount in transfers
    ]

    results = await asyncio.gather(*tasks)
    return list(results)


# AccountLock class for locking accounts
class AccountLock:
    """An asynchronous context manager that ensures only one action happens on account at a time.

    Args:
        account_number (str) The account number that identifys it.
     Attributes:
        _lock (asyncio.Lock) Lock instance.
        _ACCOUNT_LOCKS (dictionary) A dictionary of all the account numbers used AccountLock and thier lock instance. account numbers:lock instance.
    """
    _ACCOUNT_LOCKS: dict[str, asyncio.Lock] = {}

    @classmethod
    def _get_account_lock(cls, account_number: str):
        """Retrieves or creates the shared lock for a given account."""
        if account_number not in cls._ACCOUNT_LOCKS:
            cls._ACCOUNT_LOCKS[account_number] = asyncio.Lock()
        return cls._ACCOUNT_LOCKS[account_number]

    def __init__(self, account_number: str):
        self.account_number = account_number
        self._lock = self._get_account_lock(account_number)

    async def __aenter__(self):
        "Starts a lock and reports a log of it. Returns the instance itSelf"
        await self._lock.acquire()
        Bank.logger.log(f"Locking account {self.account_number}")
        return self

    async def __aexit__(self, *args) -> None:
        "Unlocks and reports a log of it."
        Bank.logger.log(f"Unlocking account {self.account_number}")
        self._lock.release()


# Bank CLI
class BankinCLI:
    """Banking complete CLI
    Args:
        bank (Bank) The bank used for all operations.
    """

    def __new__(cls, bank: Bank):
        cls.bank = bank
        return super().__new__(cls)

    @classmethod
    def _print_report(cls) -> None:
        """Prints a detailed overview of the bank, accounts, and audit log."""
        
        print("=" * 45)
        print(f"BANK REPORT: {cls.bank.name}")
        print(f"Total Accounts: {len(cls.bank)}")
        print("=" * 45)

        print("\n--- ACCOUNTS ---")
        if not cls.bank.accounts:
            print("No accounts registered.")
        else:
            for account in cls.bank.accounts:
                print(
                    f"Account #{account.account_number} | "
                    f"Owner: {account.owner} | "
                    f"Type: {account.account_type} | "
                    f"Balance: ${account.balance} | "
                    f"Transactions: {len(account)}"
                )

        print("\n--- AUDIT LOG ---")
        if not Bank.logger:
            print("No audit log entries.")
        else:
            for entry in Bank.logger:
                print(f"- {entry}")

        print("=" * 45)


    @classmethod
    async def run(cls):
        """Runs and checks the whole system is working and if it handles edge cases"""
        # System check-ups

        s1 = cls.bank.create_account("Alice", "Savings", 0.05, 0.0)
        print()
        s2 = cls.bank.create_account("Bob", "Savings", 0.05, 0.0)
        l1 = cls.bank.create_account("Alice", "Loan", 1000.0)


        s1.deposit(400)
        s1.withdraw(200) # s1: 200
        s2.deposit(200) # s2: 200
        l1.withdraw(500) # l1: -500

        transfers = [
        ("1", "3", 100.0),
        ("2", "3", 150.0),
        ("3", "1", 50.0),
        ]

        results = await async_batch_transfer(cls.bank, transfers)
        for r in results:
            print(r)

        # s1: 150
        # s2: 50
        # l1: -300

        # Edge cases handling
        print("\nExceptions:")
        print("   ", await async_transfer(cls.bank, "1", "2", 200.0))
        try:
            l1.withdraw(701)
        except Exception as e:
            print("   ", e)
        try:
            s1.deposit(-400)
        except Exception as e:
            print("   ", e)
        try:
            s2.withdraw(0)
        except Exception as e:
            print("   ", e)

        bank1 = Bank("bla bla")
        bank2 = Bank("foo")
        print("\nSame?: ", bank1 == bank2)

        iter = TransactionIterator(s1, filter="deposit")
        while True:
            try:
                print(next(iter))
            except StopIteration:
                break


asyncio.run(BankinCLI(Bank("Yoshi")).run())
BankinCLI._print_report()