#!/usr/bin/env python3
from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


# ============================================================
# Rule.java
# ============================================================

@dataclass
class Rule:
    count: int = 0
    leftSideCount: int = 0
    leftSide: Set[int] = field(default_factory=set)
    rightSide: Set[int] = field(default_factory=set)


# ============================================================
# Transaction.java
# ============================================================

@dataclass
class Transaction:
    items: Set[int]
    wi: float
    maxItem: int
    setItemRank: List[int]


# ============================================================
# AlgoFHSAR.java
# Exact conversion-style Python port for the uploaded Java files.
# ============================================================

class AlgoFHSAR:
    def __init__(self) -> None:
        self.tidcount = 0
        self.startTimestamp = 0
        self.endTimeStamp = 0
        self.minSuppRelative = 0

    def runAlgorithm(self, input_path: str, inputSAR: str, output_path: str,
                     minsup: float, minconf: float) -> None:
        self.startTimestamp = int(time.time() * 1000)

        sensitiveRules: List[Rule] = []
        checkRules: List[Rule] = []
        transactions: List[Set[int]] = []

        # Python heapq is a min-heap. We store (-wi, insertion_order, transaction)
        # so that higher wi has priority, which matches the Java PriorityQueue
        # with Transaction.compareTo().
        pwt: List[Tuple[float, int, Transaction]] = []
        insert_counter = 0

        self.readSensitiveRulesIntoMemory(inputSAR, sensitiveRules)

        self.tidcount = 0
        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()

                if not line or line[0] in "#%@":
                    continue

                lineSplited = line.split(" ")

                transaction: Set[int] = set()
                for token in lineSplited:
                    transaction.add(int(token))

                thereIsARuleSupportedByTransaction = False
                rulesContained: List[Rule] = []

                # Count rule supports exactly like the Java code
                for rule in sensitiveRules:
                    matchLeft: Set[int] = set()
                    matchRight: Set[int] = set()

                    for token in lineSplited:
                        item = int(token)

                        if len(matchLeft) != len(rule.leftSide) and item in rule.leftSide:
                            matchLeft.add(item)
                            if len(matchLeft) == len(rule.leftSide):
                                rule.leftSideCount += 1
                        elif len(matchRight) != len(rule.rightSide) and item in rule.rightSide:
                            matchRight.add(item)

                        if len(matchLeft) == len(rule.leftSide) and len(matchRight) == len(rule.rightSide):
                            rule.count += 1
                            rulesContained.append(rule)
                            thereIsARuleSupportedByTransaction = True
                            break

                if thereIsARuleSupportedByTransaction:
                    mapItemCount: Dict[int, int] = {}

                    for rule in rulesContained:
                        # Use ascending item order for deterministic tie handling.
                        # This matches the observed Java output for the uploaded test case.
                        for item in sorted(rule.leftSide):
                            mapItemCount[item] = mapItemCount.get(item, 0) + 1
                        for item in sorted(rule.rightSide):
                            mapItemCount[item] = mapItemCount.get(item, 0) + 1

                    # Java code sorts by value descending using a LinkedHashMap.
                    # For ties, we keep ascending item order to match the Java output
                    # on the uploaded data.
                    itemCountSorted = sorted(mapItemCount.items(), key=lambda kv: (-kv[1], kv[0]))
                    setItemRank = [k for k, _ in itemCountSorted]

                    # Choose first item under the same deterministic tie rule
                    maxItem = setItemRank[0]
                    mic = mapItemCount[maxItem]

                    wi = mic / math.pow(2, len(transaction) - 1)
                    td = Transaction(transaction, wi, maxItem, setItemRank)

                    heapq.heappush(pwt, (-wi, insert_counter, td))
                    insert_counter += 1

                self.tidcount += 1
                transactions.append(transaction)

        self.minSuppRelative = int(math.ceil(minsup * self.tidcount))

        while len(sensitiveRules) != 0:
            check = False
            td = None
            maxItem = 0

            while check is not True:
                _, _, tdd = heapq.heappop(pwt)

                checkingRules: List[Rule] = []
                for checkRule in checkRules:
                    if not (tdd.items.issuperset(checkRule.leftSide) and tdd.items.issuperset(checkRule.rightSide)):
                        checkingRules.append(checkRule)

                for selectedItem in tdd.setItemRank:
                    dem = 0
                    blocked = False

                    for checkingRule in checkingRules:
                        if selectedItem in checkingRule.leftSide:
                            blocked = True
                            break
                        else:
                            dem += 1

                    if blocked:
                        continue

                    if dem == len(checkingRules):
                        check = True
                        maxItem = selectedItem
                        td = tdd
                        break

            mapItemCount: Dict[int, int] = {}
            atLeastOneRule = False

            for rule in sensitiveRules:
                if td.items.issuperset(rule.leftSide) and td.items.issuperset(rule.rightSide):
                    if maxItem in rule.leftSide:
                        rule.count -= 1
                        rule.leftSideCount -= 1
                    elif maxItem in rule.rightSide:
                        rule.count -= 1
                    else:
                        atLeastOneRule = True

                        for item in sorted(rule.leftSide):
                            mapItemCount[item] = mapItemCount.get(item, 0) + 1
                        for item in sorted(rule.rightSide):
                            mapItemCount[item] = mapItemCount.get(item, 0) + 1

            td.items.remove(maxItem)

            newSensitiveRules: List[Rule] = []
            for rule in sensitiveRules:
                conf = (rule.count / float(rule.leftSideCount)) if rule.leftSideCount != 0 else 0.0

                if rule.count < self.minSuppRelative or conf < minconf:
                    if rule.count >= self.minSuppRelative:
                        checkRules.append(rule)
                else:
                    newSensitiveRules.append(rule)

            sensitiveRules = newSensitiveRules

            if atLeastOneRule:
                itemCountSorted = sorted(mapItemCount.items(), key=lambda kv: (-kv[1], kv[0]))
                newsetItemRank = [k for k, _ in itemCountSorted]

                newMaxItem = newsetItemRank[0]
                mic = mapItemCount[newMaxItem]

                wi = mic / math.pow(2, len(td.items) - 1)
                td.wi = wi
                td.maxItem = newMaxItem
                td.setItemRank = newsetItemRank

                heapq.heappush(pwt, (-wi, insert_counter, td))
                insert_counter += 1

        with open(output_path, "w", encoding="utf-8") as writer:
            for transaction in transactions:
                sorted_items = sorted(transaction)
                writer.write(" ".join(str(x) for x in sorted_items))
                writer.write("\n")

        self.endTimeStamp = int(time.time() * 1000)

    def readSensitiveRulesIntoMemory(self, inputSAR: str, rules: List[Rule]) -> None:
        with open(inputSAR, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line:
                    continue

                lineSplited = line.split("==> ")
                leftStrings = lineSplited[0].split(" ")
                rightStrings = lineSplited[1].split(" ")

                rule = Rule()

                for string in leftStrings:
                    if string:
                        rule.leftSide.add(int(string))

                for string in rightStrings:
                    if len(string) > 0 and string[0] == "#":
                        break
                    if string:
                        rule.rightSide.add(int(string))

                rules.append(rule)

    def printStats(self) -> None:
        print("=============  FSHAR 2.36 - STATS =============")
        print(" Transactions count from original database : " + str(self.tidcount))
        print(" minsup : " + str(self.minSuppRelative) + " transactions")
        print(" Total time ~ " + str(self.endTimeStamp - self.startTimestamp) + " ms")
        print("============================================")


# ============================================================
# MainTestFHSAR.java style runner
# ============================================================

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextIGB.txt"
    input_sar = script_dir / "sar.txt"
    output_path = script_dir / "output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextIGB.txt in the same folder as this Python file.")
        return

    if not input_sar.exists():
        print(f"Input file not found: {input_sar.name}")
        print("Please place sar.txt in the same folder as this Python file.")
        return

    minsup = 0.30
    minconf = 0.60

    algorithm = AlgoFHSAR()
    algorithm.runAlgorithm(str(input_path), str(input_sar), str(output_path), minsup, minconf)
    algorithm.printStats()

    print(f"\nOutput saved to: {output_path.name}\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
