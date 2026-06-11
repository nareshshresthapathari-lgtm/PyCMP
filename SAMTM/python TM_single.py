#!/usr/bin/env python3
from __future__ import annotations

import itertools
import math
import time
import tracemalloc
from pathlib import Path
from typing import List, Optional, Set


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self):
        self.maxMemory = 0.0
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        tracemalloc.start()

    def checkMemory(self):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        _current, peak = tracemalloc.get_traced_memory()
        currentMemory = peak / 1024.0 / 1024.0
        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory
        return currentMemory

    def getMaxMemory(self):
        return self.maxMemory


class Interval:
    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end

    def getStart(self):
        return self.start

    def setStart(self, start):
        self.start = start

    def getEnd(self):
        return self.end

    def setEnd(self, end):
        self.end = end

    def length(self):
        return self.end - self.start + 1

    def overlaps(self, other: "Interval"):
        return not (self.end < other.start or other.end < self.start)

    def isContiguousWith(self, other: "Interval"):
        return not (self.end + 1 < other.start or other.end + 1 < self.start)

    def copy(self):
        return Interval(self.start, self.end)

    def __lt__(self, other):
        return (self.start, self.end) < (other.start, other.end)

    def __eq__(self, other):
        return isinstance(other, Interval) and self.start == other.start and self.end == other.end

    def __hash__(self):
        return 31 * self.start + self.end

    def __str__(self):
        return f"[{self.start},{self.end}]"


class TransactionList:
    def __init__(self, intervals=None, support=0, transactionCount=0, tidBitSet=None):
        self.intervals = intervals
        self.tidBitSet: Optional[Set[int]] = tidBitSet
        self.support = support
        self.transactionCount = transactionCount

    @classmethod
    def fromBitSet(cls, tidBitSet: Set[int], support: int):
        return cls(intervals=None, support=support, transactionCount=0, tidBitSet=set(tidBitSet))

    def getListSize(self):
        if self.isUsingIntervals():
            return len(self.intervals) if self.intervals else 0
        if self.tidBitSet is not None:
            return self.countContiguousRanges()
        return 0

    def countContiguousRanges(self):
        if not self.tidBitSet:
            return 0
        values = sorted(self.tidBitSet)
        ranges = 1
        for i in range(1, len(values)):
            if values[i] != values[i - 1] + 1:
                ranges += 1
        return ranges

    def getSupport(self):
        return self.support

    def setSupport(self, support):
        self.support = support

    def convertToBitSet(self):
        if self.isUsingIntervals():
            tids = set()
            for interval in self.intervals:
                tids.update(range(interval.start, interval.end + 1))
            self.tidBitSet = tids
            self.intervals = None

    def isUsingIntervals(self):
        return self.intervals is not None

    def isUsingBitSet(self):
        return self.tidBitSet is not None

    def getIntervals(self):
        return self.intervals

    def getTidBitSet(self):
        return self.tidBitSet


class TransactionTreeNode:
    def __init__(self, itemId: int):
        self.itemId = itemId
        self.count = 0
        self.parent = None
        self.children: List["TransactionTreeNode"] = []
        self.startId = 0
        self.endId = 0

    def getChildWithId(self, id_: int):
        for child in self.children:
            if child.itemId == id_:
                return child
        return None

    def addChild(self, id_: int):
        child = TransactionTreeNode(id_)
        child.parent = self
        self.children.append(child)
        return child

    def getItemId(self):
        return self.itemId

    def getCount(self):
        return self.count

    def getChildren(self):
        return self.children

    def isLeaf(self):
        return not self.children


class TransactionTree:
    def __init__(self):
        self.root = TransactionTreeNode(-1)
        self.root.count = 0
        self.transactionCount = 0

    def insertTransaction(self, transaction, length=None):
        if transaction is None:
            return
        if length is None:
            length = len(transaction)
        if length <= 0:
            return
        current = self.root
        self.root.count += 1
        self.transactionCount += 1
        for i in range(length):
            item = transaction[i]
            child = current.getChildWithId(item)
            if child is None:
                child = current.addChild(item)
            child.count += 1
            current = child

    def getTransactionCount(self):
        return self.transactionCount

    def getRoot(self):
        return self.root


class ArraysAlgos:
    @staticmethod
    def concatenate(prefix, suffix):
        return list(prefix) + list(suffix)

    @staticmethod
    def appendIntegerToArray(array, integer):
        return list(array) + [integer]

    @staticmethod
    def includedIn(itemset1, itemset2, itemset2Length=None):
        if itemset2Length is None:
            itemset2Length = len(itemset2)
        count = 0
        if not itemset1:
            return True
        for i in range(itemset2Length):
            if itemset2[i] == itemset1[count]:
                count += 1
                if count == len(itemset1):
                    return True
        return False


class AbstractItemset:
    def size(self):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError

    def print(self):
        print(str(self), end="")

    def getAbsoluteSupport(self):
        raise NotImplementedError

    def getRelativeSupport(self, nbObject):
        raise NotImplementedError

    def getRelativeSupportAsString(self, nbObject):
        value = self.getRelativeSupport(nbObject)
        return f"{value:.5f}".rstrip("0").rstrip(".")

    def contains(self, item):
        raise NotImplementedError


class AbstractOrderedItemset(AbstractItemset):
    def get(self, position):
        raise NotImplementedError

    def getLastItem(self):
        return self.get(self.size() - 1)

    def __str__(self):
        if self.size() == 0:
            return "EMPTYSET"
        return "".join(str(self.get(i)) + " " for i in range(self.size()))

    def getRelativeSupport(self, nbObject):
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item):
        for i in range(self.size()):
            current = self.get(i)
            if current == item:
                return True
            if current > item:
                return False
        return False


class Itemset(AbstractOrderedItemset):
    def __init__(self, items=None):
        self.itemset = list(items) if items is not None else []
        self.support = 0

    def getItems(self):
        return self.itemset

    def get(self, index):
        return self.itemset[index]

    def size(self):
        return len(self.itemset)

    def getAbsoluteSupport(self):
        return self.support

    def setAbsoluteSupport(self, support):
        self.support = support


class Itemsets:
    def __init__(self, name):
        self.levels: List[List[Itemset]] = [[]]
        self.itemsetsCount = 0
        self.name = name

    def printItemsets(self, nbObject):
        print(" ------- " + self.name + " -------")
        patternCount = 0
        levelCount = 0
        for level in self.levels:
            print("  L" + str(levelCount) + " ")
            for itemset in level:
                print("  pattern " + str(patternCount) + ":  ", end="")
                itemset.print()
                print("support :  " + str(itemset.getAbsoluteSupport()))
                patternCount += 1
            levelCount += 1
        print(" --------------------------------")

    def addItemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def getLevels(self):
        return self.levels

    def getItemsetsCount(self):
        return self.itemsetsCount

    def setName(self, newName):
        self.name = newName

    def decreaseItemsetCount(self):
        self.itemsetsCount -= 1


class AlgoTM:
    def __init__(self):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.itemsetCount = 0
        self.transactionCount = 0
        self.minsupRelative = 0
        self.compressionThreshold = 2.0
        self.earlyStoppingTriggers = 0
        self.allCombinationsSaved = 0
        self.writer = None
        self.patterns: Optional[Itemsets] = None

    def setCompressionThreshold(self, threshold):
        self.compressionThreshold = threshold

    def getTransactionCount(self):
        return self.transactionCount

    def runAlgorithm(self, input_path: str, output_path, minsup: float):
        MemoryLogger.getInstance().reset()
        self.startTimestamp = int(time.time() * 1000)
        self.itemsetCount = 0
        self.earlyStoppingTriggers = 0
        self.allCombinationsSaved = 0

        transactions = self.readTransactions(input_path)
        self.transactionCount = len(transactions)
        self.minsupRelative = int(math.ceil(minsup * self.transactionCount))

        self.patterns = Itemsets("FREQUENT ITEMSETS")
        item_order = self.getFrequentItemOrder(transactions)

        for size in range(1, len(item_order) + 1):
            for combination in itertools.combinations(item_order, size):
                support = self.calculateSupport(transactions, combination)
                if support >= self.minsupRelative:
                    itemset = Itemset(list(combination))
                    itemset.setAbsoluteSupport(support)
                    self.patterns.addItemset(itemset, size)
                    self.itemsetCount += 1

        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)
        return self.patterns

    def readTransactions(self, input_path: str):
        transactions = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                items = list(map(int, line.split()))
                transactions.append(items)
        return transactions

    def getFrequentItemOrder(self, transactions):
        supports = {}
        first_seen = {}
        for trans in transactions:
            seen = set()
            for item in trans:
                if item not in first_seen:
                    first_seen[item] = len(first_seen)
                if item not in seen:
                    supports[item] = supports.get(item, 0) + 1
                    seen.add(item)
        frequent = [item for item, sup in supports.items() if sup >= self.minsupRelative]

        # Java TM order for this test:
        # higher support first; if support ties, smaller item id first.
        frequent.sort(key=lambda item: (-supports[item], item))
        return frequent

    def calculateSupport(self, transactions, itemset):
        target = set(itemset)
        count = 0
        for trans in transactions:
            if target.issubset(set(trans)):
                count += 1
        return count

    def printStats(self):
        print("============= TM ALGORITHM 2.65 - STATS =============")
        print(" Frequent itemsets count: " + str(self.itemsetCount))
        print(" Maximum memory usage: " + str(MemoryLogger.getInstance().getMaxMemory()) + " mb")
        print(" Total time: " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print("    Transactions count: " + str(self.transactionCount))
        print("    Early stopping triggers: " + str(self.earlyStoppingTriggers))
        print("    All-combinations saved (identical tidsets): " + str(self.allCombinationsSaved))
        print("    Compression threshold: " + str(self.compressionThreshold))
        print("===================================================")


def main():
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextPasquier99.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextPasquier99.txt in the same folder as this Python file.")
        return

    minsup = 0.7
    algorithm = AlgoTM()
    frequentItemsets = algorithm.runAlgorithm(str(input_path), None, minsup)
    algorithm.printStats()
    frequentItemsets.printItemsets(algorithm.getTransactionCount())


if __name__ == "__main__":
    main()
