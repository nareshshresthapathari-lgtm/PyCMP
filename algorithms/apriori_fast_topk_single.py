
#!/usr/bin/env python3
"""
Single-file Python conversion of the uploaded SPMF Apriori-FAST Top-K Java project.

Notes:
- This keeps the original class names and public method names as much as practical.
- The implementation is designed to be runnable and error-free in one file.
- Some Java-side micro-optimizations (hash-tree bucket layout, bitmap counting details)
  are simplified in Python, but the public behavior and output format are preserved.
"""

from __future__ import annotations

import argparse
import heapq
import itertools
import os
import sys
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


# ============================================================
# MemoryLogger.java
# ============================================================

class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.maxMemory = 0.0
        self.recordingMode = False
        self.outputFile: Optional[Path] = None
        self._writer = None
        self._started_trace = False

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def reset(self) -> None:
        self.maxMemory = 0.0
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_trace = True

    def checkMemory(self) -> float:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._started_trace = True
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / 1024.0 / 1024.0
        peak_mb = peak / 1024.0 / 1024.0
        if peak_mb > self.maxMemory:
            self.maxMemory = peak_mb
        if self.recordingMode and self._writer is not None:
            self._writer.write(f"{current_mb}\n")
            self._writer.flush()
        return current_mb

    def getMaxMemory(self) -> float:
        return self.maxMemory

    def startRecordingMode(self, fileName: str) -> None:
        self.recordingMode = True
        self.outputFile = Path(fileName)
        self._writer = self.outputFile.open("w", encoding="utf-8")

    def stopRecordingMode(self) -> None:
        if self.recordingMode and self._writer is not None:
            self._writer.close()
            self._writer = None
            self.recordingMode = False


# ============================================================
# ItemNameConverter.java
# ============================================================

class ItemNameConverter:
    def __init__(self, itemCount: int, firstItemName: int = 1) -> None:
        self.newNamesToOldNames = [0] * (itemCount + firstItemName)
        self.oldNamesToNewNames: Dict[int, int] = {}
        self.currentIndex = firstItemName

    def assignNewName(self, oldName: int) -> int:
        newName = self.currentIndex
        self.oldNamesToNewNames[oldName] = newName
        if newName >= len(self.newNamesToOldNames):
            self.newNamesToOldNames.extend([0] * (newName - len(self.newNamesToOldNames) + 1))
        self.newNamesToOldNames[newName] = oldName
        self.currentIndex += 1
        return newName

    def toNewName(self, oldName: int) -> int:
        return self.oldNamesToNewNames[oldName]

    def toOldName(self, newName: int) -> int:
        return self.newNamesToOldNames[newName]

    def isOldItemExisting(self, item: int) -> bool:
        return item in self.oldNamesToNewNames


# ============================================================
# AbstractItemset.java / AbstractOrderedItemset.java / Itemset.java / Itemsets.java
# ============================================================

class AbstractItemset:
    def size(self) -> int:
        raise NotImplementedError

    def getAbsoluteSupport(self) -> int:
        raise NotImplementedError

    def getRelativeSupport(self, nbObject: int) -> float:
        return self.getAbsoluteSupport() / float(nbObject)

    def getRelativeSupportAsString(self, nbObject: int) -> str:
        value = self.getRelativeSupport(nbObject)
        return f"{value:.5f}".rstrip("0").rstrip(".")

    def contains(self, item: int) -> bool:
        raise NotImplementedError

    def print(self) -> None:
        print(str(self), end="")


class AbstractOrderedItemset(AbstractItemset):
    def get(self, position: int) -> int:
        raise NotImplementedError

    def getLastItem(self) -> int:
        return self.get(self.size() - 1)

    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            current = self.get(i)
            if current == item:
                return True
            if current > item:
                return False
        return False

    def containsAll(self, itemset2: "AbstractOrderedItemset") -> bool:
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

    def isEqualTo(self, other) -> bool:
        if isinstance(other, AbstractOrderedItemset):
            if self.size() != other.size():
                return False
            return all(self.get(i) == other.get(i) for i in range(self.size()))
        if isinstance(other, (list, tuple)):
            if self.size() != len(other):
                return False
            return all(self.get(i) == other[i] for i in range(len(other)))
        return False

    def allTheSameExceptLastItemV2(self, itemset2: "AbstractOrderedItemset") -> bool:
        if itemset2.size() != self.size():
            return False
        for i in range(self.size() - 1):
            if self.get(i) != itemset2.get(i):
                return False
        return True

    def allTheSameExceptLastItem(self, itemset2: "AbstractOrderedItemset") -> Optional[int]:
        if itemset2.size() != self.size():
            return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if self.get(i) >= itemset2.get(i):
                    return None
            elif self.get(i) != itemset2.get(i):
                return None
        return itemset2.get(itemset2.size() - 1)

    def __str__(self) -> str:
        if self.size() == 0:
            return "EMPTYSET"
        return " ".join(str(self.get(i)) for i in range(self.size())) + " "


@dataclass
class Itemset(AbstractOrderedItemset):
    itemset: List[int] = field(default_factory=list)
    support: int = 0

    def getItems(self) -> List[int]:
        return self.itemset

    def size(self) -> int:
        return len(self.itemset)

    def get(self, position: int) -> int:
        return self.itemset[position]

    def getAbsoluteSupport(self) -> int:
        return self.support

    def setAbsoluteSupport(self, support: int) -> None:
        self.support = support

    def increaseTransactionCount(self) -> None:
        self.support += 1

    def cloneItemSetMinusOneItem(self, itemToRemove: int) -> "Itemset":
        return Itemset([x for x in self.itemset if x != itemToRemove], self.support)

    def cloneItemSetMinusAnItemset(self, itemsetToNotKeep: "Itemset") -> "Itemset":
        excluded = set(itemsetToNotKeep.itemset)
        return Itemset([x for x in self.itemset if x not in excluded], self.support)

    def intersection(self, itemset2: "Itemset") -> "Itemset":
        set2 = set(itemset2.itemset)
        return Itemset([x for x in self.itemset if x in set2])

    def __hash__(self) -> int:
        return hash(tuple(self.itemset))


class Itemsets:
    def __init__(self, name: str) -> None:
        self.levels: List[List[Itemset]] = [[]]
        self.itemsetsCount = 0
        self.name = name

    def printItemsets(self, nbObject: int) -> None:
        print(f" ------- {self.name} -------")
        patternCount = 0
        for levelCount, level in enumerate(self.levels):
            print(f"  L{levelCount} ")
            for itemset in level:
                print(f"  pattern {patternCount}:  ", end="")
                itemset.print()
                print(f"support :  {itemset.getAbsoluteSupport()}")
                patternCount += 1
        print(" --------------------------------")

    def addItemset(self, itemset: Itemset, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1

    def getLevels(self) -> List[List[Itemset]]:
        return self.levels

    def getItemsetsCount(self) -> int:
        return self.itemsetsCount

    def setName(self, newName: str) -> None:
        self.name = newName

    def decreaseItemsetCount(self) -> None:
        self.itemsetsCount -= 1


# ============================================================
# ArraysAlgos.java (only parts needed here)
# ============================================================

class ArraysAlgos:
    @staticmethod
    def sameAs(itemset1: Sequence[int], itemset2: Sequence[int], posRemoved: int) -> int:
        j = 0
        for i in range(len(itemset1)):
            if j == posRemoved:
                j += 1
            if itemset1[i] == itemset2[j]:
                j += 1
            elif itemset1[i] > itemset2[j]:
                return 1
            else:
                return -1
        return 0


# ============================================================
# ItemsetHashTree.java (working Python simplification)
# ============================================================

class ItemsetHashTree:
    class LeafNode:
        def __init__(self, candidates: Optional[List[List[Itemset]]] = None, nextLeafNode: Optional["ItemsetHashTree.LeafNode"] = None) -> None:
            self.candidates = candidates if candidates is not None else []
            self.nextLeafNode = nextLeafNode

    def __init__(self, itemsetSize: int, branch_count: int) -> None:
        self.branch_count = branch_count
        self.itemsetSize = itemsetSize
        self.candidateCount = 0
        self._candidates: List[Itemset] = []
        self._candidate_map: Dict[Tuple[int, ...], Itemset] = {}
        self.lastInsertedNode: Optional[ItemsetHashTree.LeafNode] = None
        self._refresh_leaf()

    def _refresh_leaf(self) -> None:
        buckets: List[List[Itemset]] = [[] for _ in range(self.branch_count)]
        for cand in self._candidates:
            idx = cand.itemset[-1] % self.branch_count
            buckets[idx].append(cand)
        self.lastInsertedNode = ItemsetHashTree.LeafNode(candidates=buckets, nextLeafNode=None)

    def insertCandidateItemset(self, itemset: Itemset) -> None:
        key = tuple(itemset.itemset)
        if key in self._candidate_map:
            return
        self.candidateCount += 1
        self._candidates.append(itemset)
        self._candidate_map[key] = itemset
        self._refresh_leaf()

    def updateSupportCount(self, transaction: Sequence[int], weight: int = 1) -> None:
        transaction_set = set(transaction)
        for candidate in self._candidates:
            if all(item in transaction_set for item in candidate.itemset):
                candidate.support += weight

    def isInTheTree(self, itemset: Sequence[int], posRemoved: int) -> bool:
        subset = tuple(item for idx, item in enumerate(itemset) if idx != posRemoved)
        return subset in self._candidate_map

    def sortAllBuckets(self) -> None:
        self._candidates.sort(key=lambda x: tuple(x.itemset))
        self._refresh_leaf()

    def iter_candidates(self) -> Iterator[Itemset]:
        return iter(self._candidates)


# ============================================================
# AlgoAprioriFAST_TopK.java
# ============================================================

class AlgoAprioriFAST_TopK:
    def __init__(self) -> None:
        self.n = 0
        self.nItemsets: List[Tuple[int, int, Itemset]] = []  # heap of (support, seq, itemset)
        self._seq = 0

        self.k = 0
        self.totalCandidateCount = 0
        self.startTimestamp = 0.0
        self.endTimestamp = 0.0
        self.itemsetCount = 0
        self.hash_tree_branch_count = 30
        self.minsupRelative = 1
        self.database: List[List[int]] = []
        self.frequentItemCount = 0
        self.DEBUG_MODE = False
        self.maxPatternLength = 1000

        self.transactionWeights: List[int] = []
        self.nameConverter: Optional[ItemNameConverter] = None
        self.useBitmapOptimization = False
        self.transactionBitmaps: List[int] = []
        self.projectionBuffer: List[int] = []
        self.databaseSize = 0
        self.itemsetsInMemory: Optional[Itemsets] = None
        self.writer = None
        self._heap_snapshot: List[Itemset] = []

    def parseLineToInts(self, line: str, result: List[int]) -> None:
        result.clear()
        number = 0
        isInteger = False
        for c in line:
            if '0' <= c <= '9':
                number = number * 10 + (ord(c) - ord('0'))
                isInteger = True
            elif c in (' ', '\t'):
                if isInteger:
                    result.append(number)
                    number = 0
                    isInteger = False
        if isInteger:
            result.append(number)

    def countSupportUsingBitmaps(self, candidatesK: ItemsetHashTree, k: int) -> None:
        for candidate in candidatesK.iter_candidates():
            candidate_bitmap = 0
            for item in candidate.itemset:
                candidate_bitmap |= (1 << item)
            support = 0
            for bitmap, weight in zip(self.transactionBitmaps, self.transactionWeights):
                if bitmap.bit_count() < k:
                    continue
                if (bitmap & candidate_bitmap) == candidate_bitmap:
                    support += weight
            candidate.support = support

    def _heap_peek_support(self) -> Optional[int]:
        if not self.nItemsets:
            return None
        return self.nItemsets[0][0]

    def saveItemsetToQueue(self, itemset: Itemset, support: int) -> None:
        heapq.heappush(self.nItemsets, (support, self._seq, itemset))
        self._seq += 1
        if len(self.nItemsets) > self.n:
            if support > self.minsupRelative:
                while len(self.nItemsets) > self.n:
                    heapq.heappop(self.nItemsets)
                peek = self._heap_peek_support()
                if peek is not None:
                    self.minsupRelative = peek

    def saveItemsetToQueueWithConversion(self, itemset: Itemset) -> None:
        assert self.nameConverter is not None
        originalItems = [self.nameConverter.toOldName(x) for x in itemset.itemset]
        originalItems.sort()
        convertedItemset = Itemset(originalItems, itemset.getAbsoluteSupport())
        self.saveItemsetToQueue(convertedItemset, itemset.getAbsoluteSupport())
        self.itemsetCount += 1

    def writeQueueToOutput(self) -> None:
        heap_items = [entry[2] for entry in self.nItemsets]
        self._heap_snapshot = heap_items[:]  # preserve heap iteration style
        if self.writer is not None:
            for itemset in heap_items:
                line = " ".join(str(x) for x in itemset.itemset) + f" #SUP: {itemset.getAbsoluteSupport()}"
                self.writer.write(line + "\n")
        else:
            if self.itemsetsInMemory is None:
                self.itemsetsInMemory = Itemsets("TOP-K FREQUENT ITEMSETS")
            for itemset in heap_items:
                self.itemsetsInMemory.addItemset(itemset, len(itemset.itemset))

    def getItemsets(self) -> Optional[Itemsets]:
        return self.itemsetsInMemory

    def processBitmapTransactions(self, rawTransactions: List[List[int]]) -> None:
        bitmaps: List[int] = []
        assert self.nameConverter is not None
        for rawTransaction in rawTransactions:
            bitmap = 0
            for item in rawTransaction:
                if self.nameConverter.isOldItemExisting(item):
                    newItem = self.nameConverter.toNewName(item)
                    bitmap |= (1 << newItem)
            if bitmap != 0:
                bitmaps.append(bitmap)
        bitmaps.sort()
        unique: List[int] = []
        weights: List[int] = []
        for bitmap in bitmaps:
            if unique and unique[-1] == bitmap:
                weights[-1] += 1
            else:
                unique.append(bitmap)
                weights.append(1)
        self.transactionBitmaps = unique
        self.transactionWeights = weights
        self.database.clear()

    def processArrayTransactions(self, rawTransactions: List[List[int]]) -> None:
        recoded: List[List[int]] = []
        assert self.nameConverter is not None
        for raw in rawTransactions:
            items = [self.nameConverter.toNewName(item) for item in raw if self.nameConverter.isOldItemExisting(item)]
            if items:
                items.sort()
                recoded.append(items)
        recoded.sort()
        self.database = []
        self.transactionWeights = []
        for trans in recoded:
            if self.database and self.database[-1] == trans:
                self.transactionWeights[-1] += 1
            else:
                self.database.append(trans)
                self.transactionWeights.append(1)

    def reduceDatabase(self, activeItems: List[bool], nextK: int) -> None:
        if self.useBitmapOptimization:
            activeMask = 0
            for item, active in enumerate(activeItems):
                if active:
                    activeMask |= (1 << item)
            projected_pairs: Dict[int, int] = {}
            for bitmap, weight in zip(self.transactionBitmaps, self.transactionWeights):
                projected = bitmap & activeMask
                if projected.bit_count() >= nextK:
                    projected_pairs[projected] = projected_pairs.get(projected, 0) + weight
            self.transactionBitmaps = sorted(projected_pairs.keys())
            self.transactionWeights = [projected_pairs[b] for b in self.transactionBitmaps]
        else:
            projected_pairs: Dict[Tuple[int, ...], int] = {}
            for trans, weight in zip(self.database, self.transactionWeights):
                proj = tuple(item for item in trans if activeItems[item])
                if len(proj) >= nextK:
                    projected_pairs[proj] = projected_pairs.get(proj, 0) + weight
            keys = sorted(projected_pairs.keys())
            self.database = [list(k) for k in keys]
            self.transactionWeights = [projected_pairs[k] for k in keys]

    def generateCandidateSizeK(self, candidatesK_1: ItemsetHashTree, level: int) -> ItemsetHashTree:
        newCandidates = ItemsetHashTree(level, self.hash_tree_branch_count)
        groups: List[List[Itemset]] = []
        for node in self._iter_leaf_nodes(candidatesK_1):
            for subgroup in node.candidates:
                if subgroup:
                    groups.append(subgroup)
        for i in range(len(groups)):
            for j in range(i, len(groups)):
                self.generate(groups[i], groups[j], candidatesK_1, newCandidates)
        newCandidates.sortAllBuckets()
        return newCandidates

    def _iter_leaf_nodes(self, tree: ItemsetHashTree) -> Iterator[ItemsetHashTree.LeafNode]:
        node = tree.lastInsertedNode
        while node is not None:
            yield node
            node = node.nextLeafNode

    def generate(self, list1: List[Itemset], list2: List[Itemset], candidatesK_1: ItemsetHashTree, newCandidates: ItemsetHashTree) -> None:
        for i in range(len(list1)):
            itemset1 = list1[i].itemset
            j = i + 1 if list1 is list2 else 0
            while j < len(list2):
                itemset2 = list2[j].itemset
                skip_outer_1 = False
                skip_outer_2 = False
                for k in range(len(itemset1)):
                    if k != len(itemset1) - 1:
                        if itemset2[k] > itemset1[k]:
                            skip_outer_1 = True
                            break
                        if itemset1[k] > itemset2[k]:
                            skip_outer_2 = True
                            break
                if skip_outer_1:
                    break
                if skip_outer_2:
                    j += 1
                    continue
                newItemset = [0] * (len(itemset1) + 1)
                if itemset2[-1] < itemset1[-1]:
                    newItemset[:-1] = itemset2[:]
                    newItemset[-1] = itemset1[-1]
                else:
                    newItemset[:-1] = itemset1[:]
                    newItemset[-1] = itemset2[-1]
                if self.allSubsetsOfSizeK_1AreFrequent(newItemset, candidatesK_1):
                    newCandidates.insertCandidateItemset(Itemset(newItemset, 0))
                j += 1

    def generateCandidate2(self, frequent1: List[int]) -> ItemsetHashTree:
        candidates = ItemsetHashTree(2, self.hash_tree_branch_count)
        for i in range(len(frequent1)):
            item1 = frequent1[i]
            for j in range(i + 1, len(frequent1)):
                item2 = frequent1[j]
                candidates.insertCandidateItemset(Itemset([item1, item2], 0))
        candidates.sortAllBuckets()
        return candidates

    def allSubsetsOfSizeK_1AreFrequent(self, itemset: List[int], hashtreeCandidatesK_1: ItemsetHashTree) -> bool:
        for posRemoved in range(len(itemset)):
            if not hashtreeCandidatesK_1.isInTheTree(itemset, posRemoved):
                return False
        return True

    def setMaximumPatternLength(self, maxPatternLength: int) -> None:
        self.maxPatternLength = maxPatternLength

    def printStats(self) -> None:
        print("=============  APRIORI-FAST TOP-K - STATS =============")
        print(f" Total time ~ {int((self.endTimestamp - self.startTimestamp) * 1000)} ms")
        print(f" Max memory ~ {MemoryLogger.getInstance().getMaxMemory():.2f} MB")
        print(f" Top-k itemsets count : {len(self.nItemsets)}")
        print(f" Candidate count : {self.totalCandidateCount}")
        print(f" Final minsup : {self.minsupRelative}")
        print("=======================================================")

    def runAlgorithm(self, kValue: int, input: str, output: Optional[str], hash_tree_branch_count: int) -> List[Tuple[int, int, Itemset]]:
        self.startTimestamp = time.perf_counter()
        self.n = kValue
        self.nItemsets = []
        self._seq = 0
        self.minsupRelative = 1

        if output is not None:
            self.writer = open(output, "w", encoding="utf-8")
            self.itemsetsInMemory = None
        else:
            self.writer = None
            self.itemsetsInMemory = Itemsets("TOP-K FREQUENT ITEMSETS")

        self.itemsetCount = 0
        self.totalCandidateCount = 0
        MemoryLogger.getInstance().reset()
        self.databaseSize = 0
        self.hash_tree_branch_count = hash_tree_branch_count

        mapItemCount: Dict[int, int] = {}
        self.database = []
        rawTransactions: List[List[int]] = []
        parsedItems: List[int] = []

        with open(input, "r", encoding="utf-8") as reader:
            for raw_line in reader:
                line = raw_line.strip()
                if not line or line[0] in "#%@":
                    continue
                self.parseLineToInts(line, parsedItems)
                transaction = list(parsedItems)
                for item in transaction:
                    mapItemCount[item] = mapItemCount.get(item, 0) + 1
                rawTransactions.append(transaction)
                self.databaseSize += 1

        if self.DEBUG_MODE:
            print(f"database size = {self.databaseSize} looking for top-{self.n} patterns")

        self.k = 1

        itemCount = len(mapItemCount)
        if itemCount >= self.n:
            itemSupports = sorted(mapItemCount.values())
            self.minsupRelative = itemSupports[itemCount - self.n]
            if self.DEBUG_MODE:
                print(f"Initial minsup raised to: {self.minsupRelative}")

        frequentItemsList = [(item, sup) for item, sup in mapItemCount.items() if sup >= self.minsupRelative]
        frequentItemsList.sort(key=lambda x: x[1])
        self.frequentItemCount = len(frequentItemsList)

        if self.frequentItemCount == 0:
            self.endTimestamp = time.perf_counter()
            MemoryLogger.getInstance().checkMemory()
            if self.writer is not None:
                self.writer.close()
            return self.nItemsets

        self.nameConverter = ItemNameConverter(self.frequentItemCount, 0)
        for item, _ in frequentItemsList:
            self.nameConverter.assignNewName(item)

        frequent1 = list(range(self.frequentItemCount))

        for item, support in frequentItemsList:
            self.saveItemsetToQueue(Itemset([item], support), support)

        if self.maxPatternLength <= 1:
            self.endTimestamp = time.perf_counter()
            MemoryLogger.getInstance().checkMemory()
            self.writeQueueToOutput()
            if self.writer is not None:
                self.writer.close()
            return self.nItemsets

        self.useBitmapOptimization = self.frequentItemCount <= 64

        if self.useBitmapOptimization:
            self.processBitmapTransactions(rawTransactions)
        else:
            self.processArrayTransactions(rawTransactions)

        self.projectionBuffer = [0] * self.frequentItemCount
        self.totalCandidateCount += len(frequent1)
        self.k = 2

        previousItemsetCount = self.itemsetCount
        previousActiveItemCount = len(frequent1)
        candidatesK: Optional[ItemsetHashTree] = None

        while self.k <= self.maxPatternLength:
            MemoryLogger.getInstance().checkMemory()

            if self.k == 2:
                candidatesK = self.generateCandidate2(frequent1)
            else:
                assert candidatesK is not None
                candidatesK = self.generateCandidateSizeK(candidatesK, self.k)

            if candidatesK.candidateCount == 0:
                break

            self.totalCandidateCount += candidatesK.candidateCount

            if self.useBitmapOptimization:
                self.countSupportUsingBitmaps(candidatesK, self.k)
            else:
                for trans, weight in zip(self.database, self.transactionWeights):
                    if len(trans) >= self.k:
                        candidatesK.updateSupportCount(trans, weight)

            activeItems = [False] * self.frequentItemCount
            activeItemCount = 0

            kept_candidates: List[Itemset] = []
            for candidate in list(candidatesK.iter_candidates()):
                if candidate.getAbsoluteSupport() >= self.minsupRelative:
                    self.saveItemsetToQueueWithConversion(candidate)
                    kept_candidates.append(candidate)
                    for item in candidate.itemset:
                        if not activeItems[item]:
                            activeItems[item] = True
                            activeItemCount += 1

            candidatesK = ItemsetHashTree(self.k, self.hash_tree_branch_count)
            for cand in kept_candidates:
                candidatesK.insertCandidateItemset(Itemset(list(cand.itemset), cand.support))
            candidatesK.sortAllBuckets()

            if self.k < self.maxPatternLength and activeItemCount > 0 and activeItemCount != previousActiveItemCount:
                self.reduceDatabase(activeItems, self.k + 1)

            if self.DEBUG_MODE:
                if self.useBitmapOptimization:
                    print(f"  Level {self.k}: {len(self.transactionBitmaps)} transactions, minsup={self.minsupRelative}")
                else:
                    print(f"  Level {self.k}: {len(self.database)} transactions, minsup={self.minsupRelative}")

            previousActiveItemCount = activeItemCount
            if previousItemsetCount == self.itemsetCount:
                break
            previousItemsetCount = self.itemsetCount
            self.k += 1

        self.writeQueueToOutput()
        self.endTimestamp = time.perf_counter()
        MemoryLogger.getInstance().checkMemory()

        if self.writer is not None:
            self.writer.close()

        return self.nItemsets


# ============================================================
# Helper / main
# ============================================================

def run_cli() -> int:
    parser = argparse.ArgumentParser(description="Apriori-FAST Top-K single-file Python conversion")
    parser.add_argument("input", nargs="?", help="Input transaction file")
    parser.add_argument("output", nargs="?", default="output.txt", help="Output file path")
    parser.add_argument("-k", "--topk", type=int, default=9, help="Top-k value")
    parser.add_argument("-b", "--branch-count", type=int, default=30, help="Hash tree branch count")
    parser.add_argument("-m", "--max-pattern-length", type=int, default=None, help="Maximum pattern length")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    if not args.input:
        print("Please provide an input file path.", file=sys.stderr)
        return 1

    algo = AlgoAprioriFAST_TopK()
    algo.DEBUG_MODE = args.debug
    if args.max_pattern_length is not None:
        algo.setMaximumPatternLength(args.max_pattern_length)

    algo.runAlgorithm(args.topk, args.input, args.output, args.branch_count)
    algo.printStats()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
