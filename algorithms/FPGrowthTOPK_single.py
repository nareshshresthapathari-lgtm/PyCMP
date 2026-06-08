#!/usr/bin/env python3
from __future__ import annotations

import math
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ============================================================
# MemoryLogger.java
# ============================================================

class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls) -> "MemoryLogger":
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self) -> float:
        return self.maxMemory

    def reset(self) -> None:
        self.maxMemory = 0.0
        if not tracemalloc.is_tracing():
            tracemalloc.start()

    def checkMemory(self) -> float:
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        current_mb = current / 1024.0 / 1024.0
        peak_mb = peak / 1024.0 / 1024.0
        if peak_mb > self.maxMemory:
            self.maxMemory = peak_mb
        return current_mb


# ============================================================
# AbstractItemset.java / AbstractOrderedItemset.java
# ============================================================

class AbstractItemset:
    def size(self) -> int:
        raise NotImplementedError

    def getAbsoluteSupport(self) -> int:
        raise NotImplementedError

    def getRelativeSupport(self, nbObject: int) -> float:
        return float(self.getAbsoluteSupport()) / float(nbObject)

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

    def __str__(self) -> str:
        if self.size() == 0:
            return "EMPTYSET"
        r = []
        for i in range(self.size()):
            r.append(str(self.get(i)))
            r.append(" ")
        return "".join(r)

    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            gi = self.get(i)
            if gi == item:
                return True
            elif gi > item:
                return False
        return False


# ============================================================
# ArraysAlgos.java
# ============================================================

class ArraysAlgos:
    @staticmethod
    def intersectTwoSortedArrays(array1: List[int], array2: List[int]) -> List[int]:
        new_array = []
        pos1 = 0
        pos2 = 0
        while pos1 < len(array1) and pos2 < len(array2):
            if array1[pos1] < array2[pos2]:
                pos1 += 1
            elif array2[pos2] < array1[pos1]:
                pos2 += 1
            else:
                new_array.append(array1[pos1])
                pos1 += 1
                pos2 += 1
        return new_array


# ============================================================
# Itemset.java / Itemsets.java
# ============================================================

@dataclass
class Itemset(AbstractOrderedItemset):
    itemset: List[int] = field(default_factory=list)
    support: int = 0

    def getItems(self) -> List[int]:
        return self.itemset

    def getAbsoluteSupport(self) -> int:
        return self.support

    def size(self) -> int:
        return len(self.itemset)

    def get(self, position: int) -> int:
        return self.itemset[position]

    def setAbsoluteSupport(self, support: int) -> None:
        self.support = support

    def increaseTransactionCount(self) -> None:
        self.support += 1

    def cloneItemSetMinusOneItem(self, itemToRemove: int) -> "Itemset":
        return Itemset([x for x in self.itemset if x != itemToRemove])

    def cloneItemSetMinusAnItemset(self, itemsetToNotKeep: "Itemset") -> "Itemset":
        return Itemset([x for x in self.itemset if not itemsetToNotKeep.contains(x)])

    def intersection(self, itemset2: "Itemset") -> "Itemset":
        return Itemset(ArraysAlgos.intersectTwoSortedArrays(self.getItems(), itemset2.getItems()))

    def __hash__(self) -> int:
        return hash(tuple(self.itemset))


class Itemsets:
    def __init__(self, name: str) -> None:
        self.levels: List[List[Itemset]] = [[]]
        self.itemsetsCount = 0
        self.name = name

    def addItemset(self, itemset: Itemset, k: int) -> None:
        while len(self.levels) <= k:
            self.levels.append([])
        self.levels[k].append(itemset)
        self.itemsetsCount += 1


# ============================================================
# FPNode.java / FPTree.java
# ============================================================

class FPNode:
    def __init__(self) -> None:
        self.itemID = -1
        self.counter = 1
        self.parent: Optional["FPNode"] = None
        self.childs: List["FPNode"] = []
        self.nodeLink: Optional["FPNode"] = None

    def getChildWithID(self, idv: int) -> Optional["FPNode"]:
        for child in self.childs:
            if child.itemID == idv:
                return child
        return None

    def toString(self, indent: str) -> str:
        output = []
        output.append(str(self.itemID))
        output.append(" (count=")
        output.append(str(self.counter))
        output.append(")\n")
        newIndent = indent + "   "
        for child in self.childs:
            output.append(newIndent + child.toString(newIndent))
        return "".join(output)

    def __str__(self) -> str:
        return str(self.itemID)


class FPTree:
    def __init__(self) -> None:
        self.headerList: Optional[List[int]] = None
        self.mapItemNodes: Dict[int, FPNode] = {}
        self.mapItemLastNode: Dict[int, FPNode] = {}
        self.root = FPNode()

    def addTransaction(self, transaction: List[int]) -> None:
        currentNode = self.root
        for item in transaction:
            child = currentNode.getChildWithID(item)
            if child is None:
                newNode = FPNode()
                newNode.itemID = item
                newNode.parent = currentNode
                currentNode.childs.append(newNode)
                currentNode = newNode
                self.fixNodeLinks(item, newNode)
            else:
                child.counter += 1
                currentNode = child

    def fixNodeLinks(self, item: int, newNode: FPNode) -> None:
        lastNode = self.mapItemLastNode.get(item)
        if lastNode is not None:
            lastNode.nodeLink = newNode
        self.mapItemLastNode[item] = newNode
        headernode = self.mapItemNodes.get(item)
        if headernode is None:
            self.mapItemNodes[item] = newNode

    def addPrefixPath(self, prefixPath: List[FPNode], mapSupportBeta: Dict[int, int], relativeMinsupp: int) -> None:
        pathCount = prefixPath[0].counter
        currentNode = self.root
        for i in range(len(prefixPath) - 1, 0, -1):
            pathItem = prefixPath[i]
            if mapSupportBeta.get(pathItem.itemID, 0) >= relativeMinsupp:
                child = currentNode.getChildWithID(pathItem.itemID)
                if child is None:
                    newNode = FPNode()
                    newNode.itemID = pathItem.itemID
                    newNode.parent = currentNode
                    newNode.counter = pathCount
                    currentNode.childs.append(newNode)
                    currentNode = newNode
                    self.fixNodeLinks(pathItem.itemID, newNode)
                else:
                    child.counter += pathCount
                    currentNode = child

    def createHeaderList(self, mapSupport: Dict[int, int]) -> None:
        self.headerList = list(self.mapItemNodes.keys())
        self.headerList.sort(key=lambda idv: (-mapSupport[idv], idv))

    def __str__(self) -> str:
        temp = "F"
        temp += " HeaderList: " + str(self.headerList) + "\n"
        temp += self.root.toString("")
        return temp


# ============================================================
# Java-like PriorityQueue for exact internal iteration order
# ============================================================

class JavaPriorityQueue:
    def __init__(self):
        self.queue: List[Itemset] = []

    def _compare(self, a: Itemset, b: Itemset) -> int:
        # Comparator.comparingInt(Itemset::getAbsoluteSupport)
        return a.getAbsoluteSupport() - b.getAbsoluteSupport()

    def add(self, e: Itemset) -> None:
        self.queue.append(e)
        self._sift_up(len(self.queue) - 1, e)

    def peek(self) -> Optional[Itemset]:
        return self.queue[0] if self.queue else None

    def poll(self) -> Optional[Itemset]:
        if not self.queue:
            return None
        s = len(self.queue) - 1
        result = self.queue[0]
        x = self.queue.pop()
        if s != 0:
            self._sift_down(0, x)
        return result

    def remove(self, e: Itemset) -> bool:
        for i, obj in enumerate(self.queue):
            if obj is e:
                self._remove_at(i)
                return True
        return False

    def _remove_at(self, i: int) -> Optional[Itemset]:
        s = len(self.queue) - 1
        if s == i:
            self.queue.pop()
        else:
            moved = self.queue.pop()
            self._sift_down_index(i, moved)
            if self.queue[i] is moved:
                self._sift_up(i, moved)
        return None

    def _sift_up(self, k: int, x: Itemset) -> None:
        while k > 0:
            parent = (k - 1) >> 1
            e = self.queue[parent]
            if self._compare(x, e) >= 0:
                break
            self.queue[k] = e
            k = parent
        self.queue[k] = x

    def _sift_down(self, k: int, x: Itemset) -> None:
        half = len(self.queue) >> 1
        while k < half:
            child = (k << 1) + 1
            c = self.queue[child]
            right = child + 1
            if right < len(self.queue) and self._compare(c, self.queue[right]) > 0:
                child = right
                c = self.queue[child]
            if self._compare(x, c) <= 0:
                break
            self.queue[k] = c
            k = child
        self.queue[k] = x

    def _sift_down_index(self, k: int, x: Itemset) -> None:
        half = len(self.queue) >> 1
        while k < half:
            child = (k << 1) + 1
            c = self.queue[child]
            right = child + 1
            if right < len(self.queue) and self._compare(c, self.queue[right]) > 0:
                child = right
                c = self.queue[child]
            if self._compare(x, c) <= 0:
                break
            self.queue[k] = c
            k = child
        self.queue[k] = x

    def size(self) -> int:
        return len(self.queue)

    def __iter__(self):
        return iter(self.queue)


# ============================================================
# AlgoFPGrowthTOPK.java
# ============================================================

class AlgoFPGrowthTOPK:
    def __init__(self) -> None:
        self.startTimestamp = 0
        self.endTime = 0
        self.transactionCount = 0
        self.minSupportRelative = 0
        self.writer = None
        self.patterns: Optional[Itemsets] = None
        self.BUFFERS_SIZE = 2000
        self.itemsetBuffer: Optional[List[int]] = None
        self.fpNodeTempBuffer: Optional[List[Optional[FPNode]]] = None
        self.maxPatternLength = 1000
        self.minPatternLength = 0
        self.n = 0
        self.nItemsets = JavaPriorityQueue()

    def runAlgorithm(self, input_path: str, output_path: Optional[str], kValue: int):
        self.startTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().reset()
        MemoryLogger.getInstance().checkMemory()

        if output_path is None:
            self.writer = None
            self.patterns = Itemsets("FREQUENT ITEMSETS")
        else:
            self.patterns = None
            self.writer = open(output_path, "w", encoding="utf-8")

        self.n = kValue
        self.nItemsets = JavaPriorityQueue()
        self.minSupportRelative = 1
        self.transactionCount = 0

        mapSupport = self.scanDatabaseToDetermineFrequencyOfSingleItems(input_path)

        if self.minPatternLength <= 1:
            itemCount = len(mapSupport)
            if itemCount >= self.n:
                itemSupports = list(mapSupport.values())
                itemSupports.sort()
                self.minSupportRelative = itemSupports[len(itemSupports) - self.n]

        tree = FPTree()

        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue

                transaction: List[int] = []
                for itemString in line.split(" "):
                    item = int(itemString)
                    if mapSupport[item] >= self.minSupportRelative:
                        transaction.append(item)

                transaction.sort(key=lambda item: (-mapSupport[item], item))
                tree.addTransaction(transaction)

        tree.createHeaderList(mapSupport)

        if tree.headerList is not None and len(tree.headerList) > 0:
            self.itemsetBuffer = [0] * self.BUFFERS_SIZE
            self.fpNodeTempBuffer = [None] * self.BUFFERS_SIZE

            for it in self.nItemsets:
                self.saveItemsetToFile(it)

            self.fpgrowth(tree, self.itemsetBuffer, 0, self.transactionCount, mapSupport)

        if self.writer is not None:
            for it in self.nItemsets:
                self.saveItemsetToFile(it)
            self.writer.close()
            self.writer = None

        self.endTime = int(time.time() * 1000)
        MemoryLogger.getInstance().checkMemory()
        return self.nItemsets

    def fpgrowth(self, tree: FPTree, prefix: List[int], prefixLength: int, prefixSupport: int, mapSupport: Dict[int, int]) -> None:
        if prefixLength == self.maxPatternLength:
            return

        singlePath = True
        position = 0

        if len(tree.root.childs) > 1:
            singlePath = False
        elif len(tree.root.childs) == 1:
            currentNode = tree.root.childs[0]
            while True:
                if len(currentNode.childs) > 1:
                    singlePath = False
                    break
                self.fpNodeTempBuffer[position] = currentNode
                position += 1
                if len(currentNode.childs) == 0:
                    break
                currentNode = currentNode.childs[0]
        else:
            singlePath = True
            position = 0

        if singlePath:
            self.saveAllCombinationsOfPrefixPath(self.fpNodeTempBuffer, position, prefix, prefixLength)
        else:
            for i in range(len(tree.headerList) - 1, -1, -1):
                item = tree.headerList[i]
                support = mapSupport[item]
                prefix[prefixLength] = item
                betaSupport = prefixSupport if prefixSupport < support else support
                self.saveItemset(prefix, prefixLength + 1, betaSupport)

                if prefixLength + 1 < self.maxPatternLength:
                    prefixPaths: List[List[FPNode]] = []
                    path = tree.mapItemNodes.get(item)
                    mapSupportBeta: Dict[int, int] = {}

                    while path is not None:
                        if path.parent is not None and path.parent.itemID != -1:
                            prefixPath: List[FPNode] = []
                            prefixPath.append(path)
                            pathCount = path.counter

                            parent = path.parent
                            while parent.itemID != -1:
                                prefixPath.append(parent)
                                mapSupportBeta[parent.itemID] = mapSupportBeta.get(parent.itemID, 0) + pathCount
                                parent = parent.parent
                            prefixPaths.append(prefixPath)
                        path = path.nodeLink

                    treeBeta = FPTree()
                    for prefixPath in prefixPaths:
                        treeBeta.addPrefixPath(prefixPath, mapSupportBeta, self.minSupportRelative)

                    if len(treeBeta.root.childs) > 0:
                        treeBeta.createHeaderList(mapSupportBeta)
                        self.fpgrowth(treeBeta, prefix, prefixLength + 1, betaSupport, mapSupportBeta)

    def saveAllCombinationsOfPrefixPath(self, fpNodeTempBuffer: List[Optional[FPNode]], position: int,
                                        prefix: List[int], prefixLength: int) -> None:
        support = 0
        i = 1
        maxv = 1 << position
        while i < maxv:
            newPrefixLength = prefixLength
            j = 0
            skip = False
            while j < position:
                isSet = i & (1 << j)
                if isSet > 0:
                    if newPrefixLength == self.maxPatternLength:
                        skip = True
                        break
                    prefix[newPrefixLength] = fpNodeTempBuffer[j].itemID
                    newPrefixLength += 1
                    support = fpNodeTempBuffer[j].counter
                j += 1
            if not skip:
                self.saveItemset(prefix, newPrefixLength, support)
            i += 1

    def scanDatabaseToDetermineFrequencyOfSingleItems(self, input_path: str) -> Dict[int, int]:
        mapSupport: Dict[int, int] = {}
        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue
                for itemString in line.split(" "):
                    item = int(itemString)
                    mapSupport[item] = mapSupport.get(item, 0) + 1
                self.transactionCount += 1
        return mapSupport

    def saveItemset(self, itemset: List[int], itemsetLength: int, support: int) -> None:
        if itemsetLength < self.minPatternLength:
            return

        itemsetArray = itemset[:itemsetLength]
        itemsetArray.sort()
        itemsetObj = Itemset(itemsetArray, support)

        self.nItemsets.add(itemsetObj)
        if self.nItemsets.size() > self.n:
            if support > self.minSupportRelative:
                lower = None
                while self.nItemsets.size() > self.n:
                    lower = self.nItemsets.peek()
                    if lower is None:
                        break
                    self.nItemsets.remove(lower)
                peeked = self.nItemsets.peek()
                if peeked is not None:
                    self.minSupportRelative = peeked.getAbsoluteSupport()

    def saveItemsetToFile(self, itemset: Itemset) -> None:
        if self.writer is not None:
            self.writer.write(str(itemset) + " #SUP: " + str(itemset.getAbsoluteSupport()))
            self.writer.write("\n")
        else:
            self.patterns.addItemset(itemset, itemset.size())

    def printStats(self) -> None:
        print("=============  FP-GROWTH (top-k version) 2.60 - STATS =============")
        t = self.endTime - self.startTimestamp
        print(" Transactions count from database : " + str(self.transactionCount))
        print(" Max memory usage: " + str(MemoryLogger.getInstance().getMaxMemory()) + " mb ")
        print(" Frequent itemsets count : " + str(self.nItemsets.size()))
        print(" Total time ~ " + str(t) + " ms")
        print("===================================================")

    def getDatabaseSize(self) -> int:
        return self.transactionCount

    def setMaximumPatternLength(self, length: int) -> None:
        self.maxPatternLength = length

    def setMinimumPatternLength(self, minPatternLength: int) -> None:
        self.minPatternLength = minPatternLength


# ============================================================
# MainTestFPGrowthTOPK_saveToFile.java style runner
# ============================================================

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextPasquier99.txt"
    output_path = script_dir / "output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextPasquier99.txt in the same folder as this Python file.")
        return

    k = 9
    algo = AlgoFPGrowthTOPK()
    algo.runAlgorithm(str(input_path), str(output_path), k)
    algo.printStats()

    print("\nOutput saved to:", output_path.name)
    print("\nContents of output file:\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
