# topk_rules_single.py
# Single-file Python conversion of SPMF TopKRules example.
# Input file format: one transaction per line, items separated by spaces.

import heapq
import os
import sys
import time
from dataclasses import dataclass, field
from functools import total_ordering
from typing import List, Set, Dict, Tuple


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0.0

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self):
        self.max_memory = 0.0

    def check_memory(self):
        # Lightweight fallback. Exact Java memory value is JVM-specific, so Python uses 0 if psutil is unavailable.
        try:
            import psutil
            process = psutil.Process(os.getpid())
            current = process.memory_info().rss / 1024.0 / 1024.0
        except Exception:
            current = 0.0
        if current > self.max_memory:
            self.max_memory = current
        return current

    def get_max_memory(self):
        return self.max_memory


class Transaction:
    def __init__(self, size: int = 0):
        self.items: List[int] = []

    def add_item(self, item: int):
        self.items.append(item)

    def get_items(self) -> List[int]:
        return self.items


class Database:
    def __init__(self):
        self.max_item = 0
        self.tids_count = 0
        self.transactions: List[Transaction] = []
        self.items_map: Dict[str, int] = {}

    def load_file(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                self.add_transaction(line.split(" "))

    def add_transaction(self, items_string: List[str]):
        transaction = Transaction(len(items_string))
        for item_string in items_string:
            if item_string == "":
                continue
            item = self.items_map.get(item_string)
            if item is None:
                item = int(item_string)
                self.items_map[item_string] = item
            if item >= self.max_item:
                self.max_item = item
            transaction.add_item(item)
        self.tids_count += 1
        self.transactions.append(transaction)
        # Java code sorts by descending order.
        transaction.items.sort(reverse=True)

    def size(self) -> int:
        return len(self.transactions)

    def get_transactions(self) -> List[Transaction]:
        return self.transactions


def contains_lex(itemset: Tuple[int, ...], item: int, max_item_in_array: int) -> bool:
    if item > max_item_in_array:
        return False
    for item_i in itemset:
        if item_i == item:
            return True
        elif item_i > item:
            return False
    return False


@total_ordering
class RuleG:
    def __init__(
        self,
        itemset1: Tuple[int, ...],
        itemset2: Tuple[int, ...],
        count: int,
        tids1: Set[int],
        common: Set[int],
        max_left: int,
        max_right: int,
    ):
        self.itemset1 = tuple(itemset1)
        self.itemset2 = tuple(itemset2)
        self.count = count
        self.tids1 = set(tids1)
        self.common = set(common)
        self.max_left = max_left
        self.max_right = max_right
        self.expand_lr = False

    def get_itemset1(self) -> Tuple[int, ...]:
        return self.itemset1

    def get_itemset2(self) -> Tuple[int, ...]:
        return self.itemset2

    def get_absolute_support(self) -> int:
        return self.count

    def get_confidence(self) -> float:
        if len(self.tids1) == 0:
            return 0.0
        return float(self.count) / len(self.tids1)

    def _cmp_key(self):
        # Same comparison order as Java RuleG.compareTo:
        # support, antecedent size, consequent size, confidence, lexicographic itemsets.
        return (
            self.get_absolute_support(),
            len(self.itemset1),
            len(self.itemset2),
            self.get_confidence(),
            self.itemset1,
            self.itemset2,
        )

    def __lt__(self, other):
        return self._cmp_key() < other._cmp_key()

    def __eq__(self, other):
        if not isinstance(other, RuleG):
            return False
        return self.itemset1 == other.itemset1 and self.itemset2 == other.itemset2

    def __str__(self):
        return f"{self._itemset_to_string(self.itemset1)} ==> {self._itemset_to_string(self.itemset2)}"

    @staticmethod
    def _itemset_to_string(itemset: Tuple[int, ...]) -> str:
        # Java appends a trailing space after each item.
        return "".join(f"{item} " for item in itemset)


class AlgoTopKRules:
    def __init__(self):
        self.time_start = 0.0
        self.time_end = 0.0
        self.min_confidence = 0.0
        self.k = 0
        self.database = None
        self.minsupp_relative = 1
        self.table_item_tids: List[Set[int]] = []
        self.table_item_count: List[int] = []
        self.k_rules: List[Tuple[RuleG, int, RuleG]] = []
        self.candidates: List[Tuple[object, int, RuleG]] = []
        self._counter = 0
        self.max_candidate_count = 0
        self.max_antecedent_size = sys.maxsize
        self.max_consequent_size = sys.maxsize

    def run_algorithm(self, k: int, min_confidence: float, database: Database):
        MemoryLogger.get_instance().reset()
        self.max_candidate_count = 0
        self.min_confidence = min_confidence
        self.database = database
        self.k = k
        self.minsupp_relative = 1
        self.table_item_tids = [set() for _ in range(database.max_item + 1)]
        self.table_item_count = [0 for _ in range(database.max_item + 1)]
        self.k_rules = []
        self.candidates = []
        self._counter = 0

        self.time_start = time.time()
        if self.max_antecedent_size >= 1 and self.max_consequent_size >= 1:
            self.scan_database(database)
            self.start()
        self.time_end = time.time()

    def start(self):
        for item_i in range(0, self.database.max_item + 1):
            if self.table_item_count[item_i] < self.minsupp_relative:
                continue
            tids_i = self.table_item_tids[item_i]

            for item_j in range(item_i + 1, self.database.max_item + 1):
                if self.table_item_count[item_j] < self.minsupp_relative:
                    continue
                tids_j = self.table_item_tids[item_j]
                common_tids = tids_i & tids_j
                support = len(common_tids)
                if support >= self.minsupp_relative:
                    self.generate_rule_size_11(item_i, tids_i, item_j, tids_j, common_tids, support)

        while self.candidates:
            _, _, rule = heapq.heappop(self.candidates)
            if rule.get_absolute_support() < self.minsupp_relative:
                break
            if rule.expand_lr:
                self.expand_l(rule)
                self.expand_r(rule)
            else:
                self.expand_r(rule)

    def generate_rule_size_11(self, item1, tid1, item2, tid2, common_tids, cardinality):
        itemset1 = (item1,)
        itemset2 = (item2,)

        rule_lr = RuleG(itemset1, itemset2, cardinality, tid1, common_tids, item1, item2)
        confidence_ij = float(cardinality) / self.table_item_count[item1]
        if confidence_ij >= self.min_confidence:
            self.save(rule_lr, cardinality)
        if len(rule_lr.get_itemset1()) < self.max_antecedent_size or len(rule_lr.get_itemset2()) < self.max_consequent_size:
            self.register_as_candidate(True, rule_lr)

        rule_rl = RuleG(itemset2, itemset1, cardinality, tid2, common_tids, item2, item1)
        confidence_ji = float(cardinality) / self.table_item_count[item2]
        if confidence_ji >= self.min_confidence:
            self.save(rule_rl, cardinality)
        if len(rule_rl.get_itemset1()) < self.max_antecedent_size or len(rule_rl.get_itemset2()) < self.max_consequent_size:
            self.register_as_candidate(True, rule_rl)

    def register_as_candidate(self, expand_lr: bool, rule: RuleG):
        rule.expand_lr = expand_lr
        self._counter += 1
        # Java candidates comparator is reverse of compareTo, so highest rule comes first.
        inv_key = _ReverseRule(rule)
        heapq.heappush(self.candidates, (inv_key, self._counter, rule))
        if len(self.candidates) > self.max_candidate_count:
            self.max_candidate_count = len(self.candidates)
        MemoryLogger.get_instance().check_memory()

    def expand_l(self, rule: RuleG):
        if len(rule.get_itemset1()) >= self.max_antecedent_size:
            return

        for candidate_item in range(rule.max_left + 1, self.database.max_item + 1):
            if self.table_item_count[candidate_item] < self.minsupp_relative:
                continue
            candidate_tids = self.table_item_tids[candidate_item]
            if not candidate_tids:
                continue
            if contains_lex(rule.get_itemset2(), candidate_item, rule.max_right):
                continue

            expanded_rule_tids = rule.common & candidate_tids
            expanded_support = len(expanded_rule_tids)
            if expanded_support < self.minsupp_relative:
                continue

            new_antecedent_tids = rule.tids1 & candidate_tids
            new_antecedent_support = len(new_antecedent_tids)
            if new_antecedent_support == 0:
                continue

            new_antecedent = rule.get_itemset1() + (candidate_item,)
            confidence = float(expanded_support) / new_antecedent_support

            expanded_rule = RuleG(
                new_antecedent,
                rule.get_itemset2(),
                expanded_support,
                new_antecedent_tids,
                expanded_rule_tids,
                candidate_item,
                rule.max_right,
            )

            if confidence >= self.min_confidence:
                self.save(expanded_rule, expanded_support)

            if len(expanded_rule.get_itemset1()) < self.max_antecedent_size or len(expanded_rule.get_itemset2()) < self.max_consequent_size:
                self.register_as_candidate(True, expanded_rule)

    def expand_r(self, rule: RuleG):
        if len(rule.get_itemset2()) >= self.max_consequent_size:
            return

        antecedent_support = len(rule.tids1)
        if antecedent_support == 0:
            return

        for candidate_item in range(rule.max_right + 1, self.database.max_item + 1):
            if self.table_item_count[candidate_item] < self.minsupp_relative:
                continue
            candidate_tids = self.table_item_tids[candidate_item]
            if not candidate_tids:
                continue
            if contains_lex(rule.get_itemset1(), candidate_item, rule.max_left):
                continue

            expanded_rule_tids = rule.common & candidate_tids
            expanded_support = len(expanded_rule_tids)
            if expanded_support < self.minsupp_relative:
                continue

            new_consequent = rule.get_itemset2() + (candidate_item,)
            confidence = float(expanded_support) / antecedent_support

            expanded_rule = RuleG(
                rule.get_itemset1(),
                new_consequent,
                expanded_support,
                rule.tids1,
                expanded_rule_tids,
                rule.max_left,
                candidate_item,
            )

            if confidence >= self.min_confidence:
                self.save(expanded_rule, expanded_support)

            if len(expanded_rule.get_itemset2()) < self.max_consequent_size:
                self.register_as_candidate(False, expanded_rule)

    def save(self, rule: RuleG, support: int):
        self._counter += 1
        heapq.heappush(self.k_rules, (rule, self._counter, rule))

        if len(self.k_rules) > self.k:
            if support > self.minsupp_relative:
                while len(self.k_rules) > self.k:
                    heapq.heappop(self.k_rules)
            self.minsupp_relative = self.k_rules[0][2].get_absolute_support()

    def scan_database(self, database: Database):
        for j, transaction in enumerate(database.get_transactions()):
            for item in transaction.get_items():
                self.table_item_tids[item].add(j)
                self.table_item_count[item] += 1

    def print_stats(self):
        print("=============  TOP-K RULES SPMF v.2.65 - STATS =============")
        print(f"Minsup : {self.minsupp_relative}")
        print(f"Rules count: {len(self.k_rules)}")
        print(f"Memory : {MemoryLogger.get_instance().get_max_memory()} mb")
        print(f"Total time : {int((self.time_end - self.time_start) * 1000)} ms")
        print("===================================================")

    def write_result_to_file(self, path: str):
        rules = [entry[2] for entry in self.k_rules]
        rules.sort()
        with open(path, "w", encoding="utf-8", newline="\n") as writer:
            for rule in rules:
                writer.write(
                    f"{rule} #SUP: {rule.get_absolute_support()} #CONF: {format_conf(rule.get_confidence())}\n"
                )

    def set_max_antecedent_size(self, max_antecedent_size: int):
        self.max_antecedent_size = max_antecedent_size

    def set_max_consequent_size(self, max_consequent_size: int):
        self.max_consequent_size = max_consequent_size


@total_ordering
class _ReverseRule:
    """Wrapper so heapq behaves like Java PriorityQueue with reversed RuleG comparison."""

    def __init__(self, rule: RuleG):
        self.rule = rule

    def __lt__(self, other):
        return other.rule < self.rule

    def __eq__(self, other):
        return self.rule == other.rule


def format_conf(value: float) -> str:
    # Java Double.toString style is close to Python str(float) for this dataset.
    return str(value)


def create_sample_context(path: str):
    sample = """1 2 4 5
2 3 5
1 2 4 5
1 2 3 5
1 2 3 4 5
2 3 4
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(sample)


def main():
    input_path = "contextIGB.txt"
    output_path = "#TopKRules_py.output.txt"
    k = 100
    min_conf = 0.4

    if len(sys.argv) >= 2:
        input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    if len(sys.argv) >= 4:
        k = int(sys.argv[3])
    if len(sys.argv) >= 5:
        min_conf = float(sys.argv[4])

    if not os.path.exists(input_path):
        create_sample_context(input_path)

    database = Database()
    database.load_file(input_path)

    algo = AlgoTopKRules()
    # Optional limits, same as Java commented code:
    # algo.set_max_antecedent_size(2)
    # algo.set_max_consequent_size(1)

    algo.run_algorithm(k, min_conf, database)
    algo.print_stats()
    algo.write_result_to_file(output_path)


if __name__ == "__main__":
    main()
