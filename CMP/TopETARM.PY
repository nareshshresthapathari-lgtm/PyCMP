#!/usr/bin/env python3
"""
TopETARM_single.py
Single-file Python version for the uploaded ETARM example.
Default settings match MainTestTopETARM.java:
    input  = contextIGB.txt
    output = output.txt
    k      = 100
    minConf= 0.8

Run:
    python TopETARM_single.py
or:
    python TopETARM_single.py contextIGB.txt output.txt --k 100 --minconf 0.8
"""

from __future__ import annotations

import argparse
import itertools
import os
import time
import tracemalloc
from typing import Iterable, List, Set, Tuple


class Transaction:
    def __init__(self, size: int = 0):
        self.items: List[int] = []

    def addItem(self, item: int) -> None:
        self.items.append(item)

    def getItems(self) -> List[int]:
        return self.items


class Database:
    def __init__(self):
        self.maxItem = 0
        self.tidsCount = 0
        self.transactions: List[Transaction] = []
        self.items = {}

    def loadFile(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ("#", "%", "@"):
                    continue
                self.addTransaction(line.split(" "))

    def addTransaction(self, itemsString: Iterable[str]) -> None:
        tokens = [x for x in itemsString if x != ""]
        transaction = Transaction(len(tokens))
        for itemString in tokens:
            if itemString not in self.items:
                self.items[itemString] = int(itemString)
            item = self.items[itemString]
            if item >= self.maxItem:
                self.maxItem = item
            transaction.addItem(item)
        self.tidsCount += 1
        transaction.items.sort(reverse=True)  # same as Java Database.java
        self.transactions.append(transaction)

    def size(self) -> int:
        return len(self.transactions)

    def getTransactions(self) -> List[Transaction]:
        return self.transactions


class RuleG:
    def __init__(self, itemset1: Tuple[int, ...], itemset2: Tuple[int, ...], count: int, tids1: Set[int], common: Set[int]):
        self.itemset1 = tuple(itemset1)
        self.itemset2 = tuple(itemset2)
        self.count = count
        self.tids1 = set(tids1)
        self.common = set(common)

    def getAbsoluteSupport(self) -> int:
        return self.count

    def getConfidence(self) -> float:
        return self.count / len(self.tids1) if self.tids1 else 0.0

    def compare_key(self):
        # Same order as uploaded RuleG.compareTo(): support, antecedent size,
        # consequent size, confidence, then lexicographic itemsets.
        return (
            self.getAbsoluteSupport(),
            len(self.itemset1),
            len(self.itemset2),
            self.getConfidence(),
            self.itemset1,
            self.itemset2,
        )

    def __str__(self) -> str:
        left = "".join(f"{x} " for x in self.itemset1)
        right = "".join(f"{x} " for x in self.itemset2)
        return f"{left} ==> {right}"


class AlgoETARM:
    def __init__(self):
        self.k = 0
        self.minConfidence = 0.0
        self.database: Database | None = None
        self.minsuppRelative = 1
        self.kRules: List[RuleG] = []
        self.timeStart = 0.0
        self.timeEnd = 0.0
        self.maxAntecedentSize = 10**9
        self.maxConsequentSize = 10**9

    def setMaxAntecedentSize(self, value: int) -> None:
        self.maxAntecedentSize = value

    def setMaxConsequentSize(self, value: int) -> None:
        self.maxConsequentSize = value

    def runAlgorithm(self, k: int, minConfidence: float, database: Database) -> None:
        tracemalloc.start()
        self.k = k
        self.minConfidence = minConfidence
        self.database = database
        self.timeStart = time.time()

        transactions = [set(t.getItems()) for t in database.getTransactions()]
        all_items = sorted(set().union(*transactions)) if transactions else []
        tidset_by_item = {
            item: {tid for tid, trans in enumerate(transactions) if item in trans}
            for item in all_items
        }

        rules: List[RuleG] = []
        n = len(all_items)
        for left_size in range(1, min(self.maxAntecedentSize, n) + 1):
            for left in itertools.combinations(all_items, left_size):
                left_set = set(left)
                left_tids = self._intersect_tidsets(left, tidset_by_item)
                if not left_tids:
                    continue

                remaining = [x for x in all_items if x not in left_set]
                max_right_size = min(self.maxConsequentSize, len(remaining))
                for right_size in range(1, max_right_size + 1):
                    for right in itertools.combinations(remaining, right_size):
                        common = set(left_tids).intersection(self._intersect_tidsets(right, tidset_by_item))
                        support = len(common)
                        if support < 1:
                            continue
                        confidence = support / len(left_tids)
                        if confidence >= minConfidence:
                            rules.append(RuleG(tuple(left), tuple(right), support, left_tids, common))

        # Top-k behavior: keep the k strongest rules, then print them ascending
        # using the same comparison order as RuleG.compareTo().
        rules.sort(key=lambda r: r.compare_key(), reverse=True)
        top_rules = rules[:k]
        top_rules.sort(key=lambda r: r.compare_key())
        self.kRules = top_rules
        self.minsuppRelative = min((r.getAbsoluteSupport() for r in self.kRules), default=1)
        self.timeEnd = time.time()

    @staticmethod
    def _intersect_tidsets(items: Iterable[int], tidset_by_item: dict[int, Set[int]]) -> Set[int]:
        iterator = iter(items)
        try:
            first = next(iterator)
        except StopIteration:
            return set()
        result = set(tidset_by_item.get(first, set()))
        for item in iterator:
            result.intersection_update(tidset_by_item.get(item, set()))
        return result

    def printStats(self) -> None:
        _, peak = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)
        print("============= ETARM SPMF v.2.65 - STATS =============")
        print(f"Minsup : {self.minsuppRelative}")
        print(f"Rules count: {len(self.kRules)}")
        print(f"Memory : {peak / 1024 / 1024} mb")
        print(f"Total time : {int((self.timeEnd - self.timeStart) * 1000)} ms")
        print("===================================================")

    def writeResultTofile(self, path: str) -> None:
        with open(path, "w", encoding="utf-8", newline="") as writer:
            for rule in self.kRules:
                writer.write(f"{rule} #SUP: {rule.getAbsoluteSupport()} #CONF: {rule.getConfidence()}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default="contextIGB.txt")
    parser.add_argument("output", nargs="?", default="output.txt")
    parser.add_argument("--k", type=int, default=100)
    parser.add_argument("--minconf", type=float, default=1.0)
    parser.add_argument("--max-antecedent", type=int, default=None)
    parser.add_argument("--max-consequent", type=int, default=None)
    args = parser.parse_args()

    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input file not found: {args.input}")

    database = Database()
    database.loadFile(args.input)

    algo = AlgoETARM()
    if args.max_antecedent is not None:
        algo.setMaxAntecedentSize(args.max_antecedent)
    if args.max_consequent is not None:
        algo.setMaxConsequentSize(args.max_consequent)

    algo.runAlgorithm(args.k, args.minconf, database)
    algo.printStats()
    algo.writeResultTofile(args.output)
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
