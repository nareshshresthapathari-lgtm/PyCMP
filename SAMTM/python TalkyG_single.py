#!/usr/bin/env python3
from __future__ import annotations

import itertools
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Set, Optional


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.max_memory = 0.0

    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def reset(self):
        self.max_memory = 0.0
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        tracemalloc.start()

    def checkMemory(self):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        _current, peak = tracemalloc.get_traced_memory()
        peak_mb = peak / 1024.0 / 1024.0
        if peak_mb > self.max_memory:
            self.max_memory = peak_mb
        return peak_mb

    def getMaxMemory(self):
        return self.max_memory


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

    def contains(self, item):
        raise NotImplementedError


class AbstractOrderedItemset(AbstractItemset):
    def get(self, position):
        raise NotImplementedError

    def __str__(self):
        if self.size() == 0:
            return "EMPTYSET"
        return "".join(f"{self.get(i)} " for i in range(self.size()))

    def getRelativeSupport(self, nbObject):
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item):
        for i in range(self.size()):
            val = self.get(i)
            if val == item:
                return True
            elif val > item:
                return False
        return False

    def containsAll(self, itemset2):
        if self.size() < itemset2.size():
            return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while not found and i < self.size():
                if self.get(i) == itemset2.get(j):
                    found = True
                elif self.get(i) > itemset2.get(j):
                    return False
                i += 1
            if not found:
                return False
        return True


class Itemset(AbstractOrderedItemset):
    def __init__(self, items=None, support=0, tidset=None):
        self.itemset = list(items) if items is not None else []
        self.support = support
        self.tidset = set(tidset) if tidset is not None else set()

    def getItems(self):
        return self.itemset

    def size(self):
        return len(self.itemset)

    def get(self, position):
        return self.itemset[position]

    def getAbsoluteSupport(self):
        return self.support

    def setAbsoluteSupport(self, support):
        self.support = support

    def __hash__(self):
        return hash(tuple(self.itemset))


class Itemsets:
    def __init__(self, name):
        self.levels = [[]]
        self.itemsetsCount = 0
        self.name = name

    def addItemset(self, itemset, k):
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1


class TransactionDatabase:
    def __init__(self):
        self.items: Set[int] = set()
        self.transactions: List[List[int]] = []
        self.maxItemID = 0

    def addTransaction(self, transaction: List[int]):
        self.transactions.append(transaction)
        self.items.update(transaction)
        if transaction:
            self.maxItemID = max(self.maxItemID, max(transaction))

    def loadFile(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                self.addTransaction(list(map(int, line.split())))

    def size(self):
        return len(self.transactions)

    def getTransactions(self):
        return self.transactions

    def getMaxItemID(self):
        return self.maxItemID


class TriangularMatrix:
    def __init__(self, elementCount):
        self.elementCount = elementCount
        self.matrix = [[0] * (elementCount - i - 1) for i in range(elementCount - 1)]

    def incrementCount(self, i, j):
        if j < i:
            self.matrix[self.elementCount - i - 1][j] += 1
        else:
            self.matrix[self.elementCount - j - 1][i] += 1

    def getSupportForItems(self, i, j):
        if j < i:
            return self.matrix[self.elementCount - i - 1][j]
        return self.matrix[self.elementCount - j - 1][i]


class GeneratorHashTable:
    def __init__(self, size):
        self.tableBySupport = [[] for _ in range(size)]

    def containsSubsetWithSameSupport(self, itemset, support):
        hashcode = support % len(self.tableBySupport)
        for itemsetX in self.tableBySupport[hashcode]:
            if (
                itemsetX.getAbsoluteSupport() == support
                and itemsetX.size() < len(itemset)
                and self.isSubset(itemsetX.getItems(), itemset)
            ):
                return True
        return False

    def isSubset(self, subset, superset):
        if len(subset) > len(superset):
            return False
        j = 0
        for i in range(len(subset)):
            while j < len(superset) and superset[j] < subset[i]:
                j += 1
            if j >= len(superset) or superset[j] != subset[i]:
                return False
            j += 1
        return True

    def put(self, itemset, support):
        hashcode = support % len(self.tableBySupport)
        self.tableBySupport[hashcode].append(itemset)


class AlgoTalkyG_Bitset:
    def __init__(self):
        self.minsupRelative = 0
        self.database = None
        self.startTimestamp = 0
        self.endTime = 0
        self.frequentGenerators = None
        self.writer = None
        self.generatorCount = 0
        self.matrix = None
        self.generatorHash = None
        self.maximumPatternLength = 2**31 - 1
        self.item_tidsets: Dict[int, Set[int]] = {}
        self.support_cache: Dict[tuple, Set[int]] = {}

    def setMaximumPatternLength(self, maximumPatternLength):
        self.maximumPatternLength = maximumPatternLength

    def runAlgorithm(self, output, database, minsup, useTriangularMatrixOptimization, hashTableSize):
        MemoryLogger.getInstance().reset()

        if output is None:
            self.writer = None
            self.frequentGenerators = Itemsets("FREQUENT GENERATORS")
        else:
            self.frequentGenerators = None
            self.writer = open(output, "w", encoding="utf-8")

        self.generatorHash = GeneratorHashTable(hashTableSize)
        self.generatorCount = 0
        self.database = database
        self.startTimestamp = int(time.time() * 1000)
        self.minsupRelative = max(1, int((minsup * database.size()) + 0.999999999))

        self.item_tidsets = {}
        maxItemId = self.calculateSupportSingleItems(database, self.item_tidsets)

        if useTriangularMatrixOptimization:
            self.matrix = TriangularMatrix(maxItemId + 1)
            for transaction in database.getTransactions():
                for i in range(len(transaction)):
                    for j in range(i + 1, len(transaction)):
                        self.matrix.incrementCount(transaction[i], transaction[j])

        hasFullColumn = any(len(tids) == database.size() for tids in self.item_tidsets.values())
        if not hasFullColumn:
            self.saveGenerator([], set(range(database.size())))

        frequentItems = [
            item for item, tids in self.item_tidsets.items()
            if len(tids) >= self.minsupRelative and len(tids) < database.size()
        ]
        frequentItems.sort(key=lambda x: (len(self.item_tidsets[x]), x))

        for item in frequentItems:
            self.support_cache[(item,)] = set(self.item_tidsets[item])

        for idx, item in enumerate(frequentItems):
            tids = self.support_cache[(item,)]
            self.saveGenerator([item], tids)

            if self.maximumPatternLength <= 1:
                continue

            suffixes = []
            suffix_tids = []
            for j in range(idx + 1, len(frequentItems)):
                itemJ = frequentItems[j]
                if useTriangularMatrixOptimization:
                    supportIJ = self.matrix.getSupportForItems(item, itemJ)
                    if supportIJ < self.minsupRelative:
                        continue
                inter = tids & self.item_tidsets[itemJ]
                if len(inter) < self.minsupRelative:
                    continue
                if inter == tids or inter == self.item_tidsets[itemJ]:
                    continue
                suffixes.append(itemJ)
                suffix_tids.append(inter)
                self.support_cache[tuple(sorted((item, itemJ)))] = set(inter)

            if suffixes:
                self.processEquivalenceClass([item], suffixes, suffix_tids)

        if self.writer is not None:
            self.writer.close()
            self.writer = None

        MemoryLogger.getInstance().checkMemory()
        self.endTime = int(time.time() * 1000)
        return self.frequentGenerators

    def calculateSupportSingleItems(self, database, mapItemTIDS):
        maxItemId = 0
        for tid, transaction in enumerate(database.getTransactions()):
            for item in transaction:
                tids = mapItemTIDS.get(item)
                if tids is None:
                    tids = set()
                    mapItemTIDS[item] = tids
                    if item > maxItemId:
                        maxItemId = item
                tids.add(tid)
        return maxItemId

    def processEquivalenceClass(self, prefix, equivalenceClassItems, equivalenceClassTidsets):
        for idx, suffix in enumerate(equivalenceClassItems):
            candidate = prefix + [suffix]
            tids = equivalenceClassTidsets[idx]
            self.saveGenerator(candidate, tids)

            if len(candidate) >= self.maximumPatternLength:
                continue

            newItems = []
            newTidsets = []
            for j in range(idx + 1, len(equivalenceClassItems)):
                suffixJ = equivalenceClassItems[j]
                tidsJ = equivalenceClassTidsets[j]
                inter = tids & tidsJ
                if len(inter) < self.minsupRelative:
                    continue

                cand_plus = tuple(sorted(candidate + [suffixJ]))
                # generator check using all proper subsets
                skip = False
                for r in range(1, len(cand_plus)):
                    for subset in itertools.combinations(cand_plus, r):
                        subset_tids = self.computeTidset(subset)
                        if len(subset_tids) == len(inter):
                            skip = True
                            break
                    if skip:
                        break
                if skip:
                    continue

                newItems.append(suffixJ)
                newTidsets.append(inter)
                self.support_cache[cand_plus] = set(inter)

            if newItems:
                self.processEquivalenceClass(candidate, newItems, newTidsets)

    def computeTidset(self, items):
        key = tuple(sorted(items))
        if key in self.support_cache:
            return self.support_cache[key]
        tids = set(range(self.database.size()))
        for item in key:
            tids &= self.item_tidsets[item]
        self.support_cache[key] = set(tids)
        return tids

    def saveGenerator(self, itemset, tidset):
        support = len(tidset)
        if itemset and self.generatorHash.containsSubsetWithSameSupport(itemset, support):
            return
        self.generatorCount += 1
        obj = Itemset(itemset, support=support, tidset=tidset)
        self.generatorHash.put(obj, support)
        if self.writer is not None:
            if len(itemset) == 0:
                self.writer.write(f"#SUP: {support}\n")
            else:
                self.writer.write(" ".join(map(str, itemset)) + f" #SUP: {support}\n")
        else:
            self.frequentGenerators.addItemset(obj, len(itemset))

    def printStats(self):
        print("============= TalkyG Bitset - STATS =============")
        print(" Frequent generators count : " + str(self.generatorCount))
        print(" Total time ~ " + str(self.endTime - self.startTimestamp) + " ms")
        print(" Maximum memory usage : " + str(MemoryLogger.getInstance().getMaxMemory()) + " mb")
        print("===================================================")


def main():
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextZart.txt"
    output_path = script_dir / "#TalkyG_Py_output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextZart.txt in the same folder as this Python file.")
        return

    minsup = 0.7
    useTriangularMatrixOptimization = True
    hashTableSize = 500

    database = TransactionDatabase()
    database.loadFile(str(input_path))

    algo = AlgoTalkyG_Bitset()
    algo.setMaximumPatternLength(10)
    algo.runAlgorithm(str(output_path), database, minsup, useTriangularMatrixOptimization, hashTableSize)
    algo.printStats()

    print("\nOutput saved to:", output_path.name)
    print("\nContents of output file:\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
