#!/usr/bin/env python3
from __future__ import annotations

import math
import time
import tracemalloc
from pathlib import Path
from typing import List, Optional


# ============================================================
# MemoryLogger.java
# ============================================================

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


# ============================================================
# AbstractItemset.java / AbstractOrderedItemset.java
# ============================================================

class AbstractItemset:
    def size(self):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError

    def getAbsoluteSupport(self):
        raise NotImplementedError

    def getRelativeSupport(self, nbObject):
        raise NotImplementedError

    def print(self):
        print(str(self), end="")

    def contains(self, item):
        raise NotImplementedError


class AbstractOrderedItemset(AbstractItemset):
    def getAbsoluteSupport(self):
        raise NotImplementedError

    def size(self):
        raise NotImplementedError

    def get(self, position):
        raise NotImplementedError

    def getLastItem(self):
        return self.get(self.size() - 1)

    def __str__(self):
        if self.size() == 0:
            return "EMPTYSET"
        return "".join(f"{self.get(i)} " for i in range(self.size()))

    def getRelativeSupport(self, nbObject):
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item):
        for i in range(self.size()):
            value = self.get(i)
            if value == item:
                return True
            elif value > item:
                return False
        return False

    def containsAll(self, itemset2):
        if self.size() < itemset2.size():
            return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while (not found) and i < self.size():
                if self.get(i) == itemset2.get(j):
                    found = True
                elif self.get(i) > itemset2.get(j):
                    return False
                i += 1
            if not found:
                return False
        return True

    def isEqualTo(self, other):
        if hasattr(other, "size"):
            if self.size() != other.size():
                return False
            for i in range(other.size()):
                if other.get(i) != self.get(i):
                    return False
            return True
        if self.size() != len(other):
            return False
        for i, value in enumerate(other):
            if value != self.get(i):
                return False
        return True

    def allTheSameExceptLastItemV2(self, itemset2):
        if itemset2.size() != self.size():
            return False
        for i in range(self.size() - 1):
            if self.get(i) != itemset2.get(i):
                return False
        return True

    def allTheSameExceptLastItem(self, itemset2):
        if itemset2.size() != self.size():
            return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if self.get(i) >= itemset2.get(i):
                    return None
            elif self.get(i) != itemset2.get(i):
                return None
        return itemset2.get(itemset2.size() - 1)


# ============================================================
# ArraysAlgos.java
# ============================================================

class ArraysAlgos:
    @staticmethod
    def intersectTwoSortedArrays(array1, array2):
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

class Itemset(AbstractOrderedItemset):
    def __init__(self, items=None, support=0):
        if items is None:
            self.itemset = []
        elif isinstance(items, int):
            self.itemset = [items]
        else:
            self.itemset = list(items)
        self.support = support

    def getItems(self):
        return self.itemset

    def getAbsoluteSupport(self):
        return self.support

    def size(self):
        return len(self.itemset)

    def get(self, position):
        return self.itemset[position]

    def setAbsoluteSupport(self, support):
        self.support = support

    def increaseTransactionCount(self):
        self.support += 1

    def cloneItemSetMinusOneItem(self, itemToRemove):
        return Itemset([x for x in self.itemset if x != itemToRemove])

    def cloneItemSetMinusAnItemset(self, itemsetToNotKeep):
        return Itemset([x for x in self.itemset if not itemsetToNotKeep.contains(x)])

    def intersection(self, itemset2):
        intersection = ArraysAlgos.intersectTwoSortedArrays(self.getItems(), itemset2.getItems())
        return Itemset(intersection)

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

    def getLevels(self):
        return self.levels

    def getItemsetsCount(self):
        return self.itemsetsCount

    def setName(self, newName):
        self.name = newName

    def decreaseItemsetCount(self):
        self.itemsetsCount -= 1


# ============================================================
# AlgoLinearTable.java
# Direct conversion-style Python port
# ============================================================

class AlgoLinearTable:
    FILE_BUFFER_SIZE = 65536
    INITIAL_TABLE_CAPACITY = 4096
    INITIAL_ITEM_ARRAY_SIZE = 1024
    INITIAL_DB_CAPACITY = 4096

    def __init__(self):
        self.DEBUG_MODE = False

    def runAlgorithm(self, input_path, output_path, minsupp):
        if minsupp < 0 or minsupp > 1.0:
            raise ValueError("minsupp must be in (0, 1]")

        self.resetState()

        MemoryLogger.getInstance().reset()
        self.startTimestamp = int(time.time() * 1000)
        self.saveToMemory = (output_path is None)

        if self.saveToMemory:
            self.frequentItemsets = Itemsets("FREQUENT ITEMSETS")
        else:
            self.writer = open(output_path, "w", encoding="utf-8")

        try:
            self.readDatabaseAndCountSupports(input_path)

            if self.transactionCount == 0:
                self.endTimestamp = int(time.time() * 1000)
                return self.frequentItemsets

            self.minsupAbsolute = math.ceil(minsupp * self.transactionCount)
            if self.minsupAbsolute == 0:
                self.minsupAbsolute = 1

            self.buildItemRankings()
            self.useLongRepresentation = (self.frequentItemCount <= 64)

            self.transactionBuffer = [0] * self.maxTransactionLength
            self.itemsetBuffer = [0] * self.maxTransactionLength

            self.outputSingleItemsets()

            if self.frequentItemCount <= 1:
                self.endTimestamp = int(time.time() * 1000)
                return self.frequentItemsets

            MemoryLogger.getInstance().checkMemory()

            self.buildLinearTableFromMemory()
            self.transactionDatabase = None

            if self.DEBUG_MODE:
                self.printHeaderTable()
                self.printLinearTable()
                self.printReconstructedDatabase()

            self.freeConstructionArrays()
            MemoryLogger.getInstance().checkMemory()

            if self.useLongRepresentation:
                self.mineFrequentItemsetsLong()
            else:
                self.mineFrequentItemsetsLongArray()

            MemoryLogger.getInstance().checkMemory()

        finally:
            if self.writer is not None:
                self.writer.close()
                self.writer = None

        self.endTimestamp = int(time.time() * 1000)
        return self.frequentItemsets

    def readDatabaseAndCountSupports(self, input_path):
        self.transactionCount = 0
        self.transactionDatabaseSize = 0
        self.maxItemId = 0
        self.maxTransactionLength = 0

        currentArraySize = self.INITIAL_ITEM_ARRAY_SIZE
        self.itemSupportArray = [0] * currentArraySize
        self.transactionDatabase = [None] * self.INITIAL_DB_CAPACITY

        tempItems = [0] * 64

        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line or line[0] in "#%@":
                    continue

                itemCount = 0
                length = len(line)
                num = 0
                hasNum = False

                for i in range(length + 1):
                    c = line[i] if i < length else " "
                    if "0" <= c <= "9":
                        num = num * 10 + (ord(c) - 48)
                        hasNum = True
                    elif hasNum:
                        if itemCount >= len(tempItems):
                            tempItems.extend([0] * len(tempItems))
                        tempItems[itemCount] = num
                        itemCount += 1

                        if num >= currentArraySize:
                            newSize = max(currentArraySize * 2, num + 1)
                            self.itemSupportArray.extend([0] * (newSize - currentArraySize))
                            currentArraySize = newSize

                        if num > self.maxItemId:
                            self.maxItemId = num
                        self.itemSupportArray[num] += 1

                        num = 0
                        hasNum = False

                if itemCount > 0:
                    if self.transactionDatabaseSize >= len(self.transactionDatabase):
                        self.transactionDatabase.extend([None] * len(self.transactionDatabase))

                    self.transactionDatabase[self.transactionDatabaseSize] = tempItems[:itemCount]
                    self.transactionDatabaseSize += 1
                    self.transactionCount += 1

                    if itemCount > self.maxTransactionLength:
                        self.maxTransactionLength = itemCount

        self.itemSupportArray = self.itemSupportArray[:self.maxItemId + 1]
        self.transactionDatabase = self.transactionDatabase[:self.transactionDatabaseSize]

    def buildItemRankings(self):
        pairs = []
        self.itemIdToRank = [-1] * (self.maxItemId + 1)

        for itemId, support in enumerate(self.itemSupportArray):
            if support >= self.minsupAbsolute:
                pairs.append((itemId, support))

        pairs.sort(key=lambda x: (-x[1], x[0]))

        self.frequentItemCount = len(pairs)
        self.rankToItemId = [itemId for itemId, _support in pairs]

        for rank, (itemId, _support) in enumerate(pairs):
            self.itemIdToRank[itemId] = rank

    def initializeLinearTableArrays(self, capacity):
        self.linearTableCapacity = capacity

        self.nodeItemRank = [0] * capacity
        self.nodeParentIndex = [0] * capacity
        self.nodeChildIndex = [0] * capacity
        self.nodeSiblingIndex = [0] * capacity

        self.nodePrevIndex = [0] * capacity
        self.nodeFrequency = [0] * capacity

        if self.useLongRepresentation:
            self.nodeBinaryLong = [0] * capacity
            self.nodeBinaryArray = None
        else:
            self.nodeBinaryLong = None
            self.nodeBinaryArray = [None] * capacity

    def growLinearTableArrays(self):
        newCapacity = self.linearTableCapacity * 2
        add = newCapacity - self.linearTableCapacity

        self.nodeItemRank.extend([0] * add)
        self.nodeParentIndex.extend([0] * add)
        self.nodeChildIndex.extend([0] * add)
        self.nodeSiblingIndex.extend([0] * add)
        self.nodePrevIndex.extend([0] * add)
        self.nodeFrequency.extend([0] * add)

        if self.useLongRepresentation:
            self.nodeBinaryLong.extend([0] * add)
        else:
            self.nodeBinaryArray.extend([None] * add)

        self.linearTableCapacity = newCapacity

    def freeConstructionArrays(self):
        self.nodeItemRank = None
        self.nodeParentIndex = None
        self.nodeChildIndex = None
        self.nodeSiblingIndex = None
        self.rootChildByRank = None

    def buildLinearTableFromMemory(self):
        self.initializeLinearTableArrays(self.INITIAL_TABLE_CAPACITY)
        self.linearTableSize = 1

        self.nodeItemRank[0] = -1
        self.nodeFrequency[0] = 0

        self.headerTable = [0] * self.frequentItemCount
        self.rootChildByRank = [0] * self.frequentItemCount
        self.firstRootChildIndex = 0

        for transaction in self.transactionDatabase:
            filteredLength = self.filterAndSortTransaction(transaction)
            if filteredLength > 0:
                self.insertTransaction(self.transactionBuffer, filteredLength)

    def filterAndSortTransaction(self, transaction):
        count = 0

        for item in transaction:
            if item <= self.maxItemId:
                rank = self.itemIdToRank[item]
                if rank >= 0:
                    self.transactionBuffer[count] = rank
                    count += 1

        if count > 1:
            self.transactionBuffer[:count] = sorted(self.transactionBuffer[:count])

        return count

    def insertTransaction(self, ranks, length):
        parentIndex = 0
        currentBinaryLong = 0
        currentBinaryArray = None if self.useLongRepresentation else [0] * ((self.frequentItemCount + 63) // 64)

        for i in range(length):
            rank = ranks[i]

            if self.useLongRepresentation:
                currentBinaryLong |= (1 << rank)
            else:
                wordIndex = rank // 64
                bitIndex = rank % 64
                currentBinaryArray[wordIndex] |= (1 << bitIndex)

            existingIndex = self.findChildByRank(parentIndex, rank)

            if existingIndex > 0:
                self.nodeFrequency[existingIndex] += 1
                parentIndex = existingIndex
            else:
                if self.linearTableSize >= self.linearTableCapacity:
                    self.growLinearTableArrays()

                newIndex = self.linearTableSize
                self.linearTableSize += 1

                self.nodeItemRank[newIndex] = rank
                self.nodeParentIndex[newIndex] = parentIndex
                self.nodeChildIndex[newIndex] = 0
                self.nodeSiblingIndex[newIndex] = 0
                self.nodePrevIndex[newIndex] = 0
                self.nodeFrequency[newIndex] = 1

                if self.useLongRepresentation:
                    self.nodeBinaryLong[newIndex] = currentBinaryLong
                else:
                    self.nodeBinaryArray[newIndex] = currentBinaryArray.copy()

                self.linkNewNode(parentIndex, rank, newIndex)

                prevOccurrence = self.headerTable[rank]
                if prevOccurrence > 0:
                    self.nodePrevIndex[newIndex] = prevOccurrence
                self.headerTable[rank] = newIndex

                parentIndex = newIndex

    def findChildByRank(self, parentIndex, rank):
        if parentIndex == 0:
            return self.rootChildByRank[rank]

        childIdx = self.nodeChildIndex[parentIndex]
        while childIdx > 0:
            if self.nodeItemRank[childIdx] == rank:
                return childIdx
            childIdx = self.nodeSiblingIndex[childIdx]
        return 0

    def linkNewNode(self, parentIndex, rank, newIndex):
        if parentIndex == 0:
            self.rootChildByRank[rank] = newIndex
            self.nodeSiblingIndex[newIndex] = self.firstRootChildIndex
            self.firstRootChildIndex = newIndex
        else:
            self.nodeSiblingIndex[newIndex] = self.nodeChildIndex[parentIndex]
            self.nodeChildIndex[parentIndex] = newIndex

    def mineFrequentItemsetsLong(self):
        prev = self.nodePrevIndex
        freq = self.nodeFrequency
        binary = self.nodeBinaryLong
        header = self.headerTable
        minSup = self.minsupAbsolute

        for groupRank in range(1, self.frequentItemCount):
            groupBit = 1 << groupRank
            maxPossibleSupport = self.itemSupportArray[self.rankToItemId[groupRank]]
            maxPrefix = (1 << groupRank) - 1
            prefix = 1

            while prefix <= maxPrefix:
                candidate = prefix | groupBit
                support = self.calculateSupportLong(candidate, groupRank, maxPossibleSupport, prev, freq, binary,
                                                    header, minSup)

                if support >= minSup:
                    self.outputItemsetFromBits(candidate, groupRank, support)
                    prefix += 1
                else:
                    lowBit = prefix & (-prefix)
                    prefix = prefix + lowBit
                    self.pruningCount += 1

    def calculateSupportLong(self, candidate, rightmostRank, maxPossibleSupport, prev, freq, binary, header, minSup):
        position = header[rightmostRank]
        support = 0
        remaining = maxPossibleSupport

        while position > 0:
            nodeBinary = binary[position]
            nodeFreq = freq[position]

            if (nodeBinary & candidate) == candidate:
                support += nodeFreq

            remaining -= nodeFreq
            if support + remaining < minSup:
                return support

            position = prev[position]

        return support

    def outputItemsetFromBits(self, bits, maxRank, support):
        count = 0
        for rank in range(maxRank + 1):
            if (bits & (1 << rank)) != 0:
                self.itemsetBuffer[count] = self.rankToItemId[rank]
                count += 1
        self.saveItemsetFromBuffer(count, support)

    def mineFrequentItemsetsLongArray(self):
        numWords = (self.frequentItemCount + 63) // 64

        prev = self.nodePrevIndex
        freq = self.nodeFrequency
        binaryArrays = self.nodeBinaryArray
        header = self.headerTable
        minSup = self.minsupAbsolute

        prefix = [0] * numWords
        candidate = [0] * numWords

        for groupRank in range(1, self.frequentItemCount):
            groupWordIndex = groupRank // 64
            groupBitIndex = groupRank % 64
            groupBit = 1 << groupBitIndex
            maxPossibleSupport = self.itemSupportArray[self.rankToItemId[groupRank]]

            for i in range(numWords):
                prefix[i] = 0
            prefix[0] = 1

            limitWord = (groupRank - 1) // 64
            lastBitInLimitWord = (groupRank - 1) % 64
            limitMask = -1 if lastBitInLimitWord == 63 else ((1 << (lastBitInLimitWord + 1)) - 1)

            while True:
                candidate[:] = prefix[:]
                candidate[groupWordIndex] |= groupBit

                support = self.calculateSupportLongArray(candidate, groupRank, maxPossibleSupport, prev, freq,
                                                         binaryArrays, header, minSup)

                if support >= minSup:
                    self.outputItemsetFromBitsArray(candidate, groupRank, support)
                    if not self.incrementPrefix(prefix, limitWord, limitMask):
                        break
                else:
                    if not self.prunePrefix(prefix, limitWord, limitMask):
                        break
                    self.pruningCount += 1

    def incrementPrefix(self, prefix, limitWord, limitMask):
        for w in range(limitWord + 1):
            prefix[w] += 1
            if prefix[w] != 0:
                if w == limitWord and (prefix[w] & ~limitMask) != 0:
                    return False
                return True
        return False

    def prunePrefix(self, prefix, limitWord, limitMask):
        for w in range(limitWord + 1):
            if prefix[w] != 0:
                lowBit = prefix[w] & -prefix[w]
                prefix[w] = prefix[w] + lowBit
                if w == limitWord and (prefix[w] & ~limitMask) != 0:
                    return False
                return True
        return False

    def calculateSupportLongArray(self, candidate, rightmostRank, maxPossibleSupport, prev, freq, binaryArrays,
                                  header, minSup):
        position = header[rightmostRank]
        support = 0
        remaining = maxPossibleSupport
        maxWord = rightmostRank // 64
        cand0 = candidate[0]

        while position > 0:
            nodeRep = binaryArrays[position]
            nodeFreq = freq[position]

            contained = ((nodeRep[0] & cand0) == cand0)
            for w in range(1, maxWord + 1):
                if contained and ((nodeRep[w] & candidate[w]) != candidate[w]):
                    contained = False

            if contained:
                support += nodeFreq

            remaining -= nodeFreq
            if support + remaining < minSup:
                return support

            position = prev[position]

        return support

    def outputItemsetFromBitsArray(self, bits, maxRank, support):
        count = 0
        for rank in range(maxRank + 1):
            wordIndex = rank // 64
            bitIndex = rank % 64
            if (bits[wordIndex] & (1 << bitIndex)) != 0:
                self.itemsetBuffer[count] = self.rankToItemId[rank]
                count += 1
        self.saveItemsetFromBuffer(count, support)

    def saveItemsetFromBuffer(self, length, support):
        self.frequentItemsetCount += 1
        arr = sorted(self.itemsetBuffer[:length])

        if self.saveToMemory:
            itemsetObj = Itemset(arr)
            itemsetObj.setAbsoluteSupport(support)
            self.frequentItemsets.addItemset(itemsetObj, length)
        else:
            self.writer.write(" ".join(map(str, arr)) + f" #SUP: {support}\n")

    def outputSingleItemsets(self):
        for rank in range(self.frequentItemCount):
            itemId = self.rankToItemId[rank]
            support = self.itemSupportArray[itemId]
            self.frequentItemsetCount += 1

            if self.saveToMemory:
                itemsetObj = Itemset([itemId])
                itemsetObj.setAbsoluteSupport(support)
                self.frequentItemsets.addItemset(itemsetObj, 1)
            else:
                self.writer.write(f"{itemId} #SUP: {support}\n")

    def resetState(self):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.frequentItemsetCount = 0
        self.pruningCount = 0
        self.minsupAbsolute = 0
        self.transactionCount = 0
        self.frequentItemsets = None
        self.maxTransactionLength = 0
        self.writer = None
        self.saveToMemory = False

        self.transactionDatabase = None
        self.transactionDatabaseSize = 0

        self.itemSupportArray = None
        self.maxItemId = 0
        self.itemIdToRank = None
        self.rankToItemId = None
        self.frequentItemCount = 0

        self.linearTableSize = 0
        self.linearTableCapacity = 0
        self.nodeItemRank = None
        self.nodeParentIndex = None
        self.nodeChildIndex = None
        self.nodeSiblingIndex = None
        self.rootChildByRank = None
        self.nodePrevIndex = None
        self.nodeFrequency = None
        self.nodeBinaryLong = None
        self.nodeBinaryArray = None

        self.headerTable = None
        self.firstRootChildIndex = 0
        self.useLongRepresentation = False
        self.transactionBuffer = None
        self.itemsetBuffer = None

    def printStats(self):
        longRepresentation = "(LONG)" if self.useLongRepresentation else "(LONG_ARRAY)"
        print("============= LINEAR TABLE ALGORITHM 2.65 " + longRepresentation + " =============")
        print(" Frequent itemsets count: " + str(self.frequentItemsetCount))
        print(" Maximum memory usage: " + str(MemoryLogger.getInstance().getMaxMemory()) + " mb")
        print(" Total time: " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print("===========================================================")

    # Debug helper stubs
    def printLinearTable(self):
        pass

    def printHeaderTable(self):
        pass

    def printReconstructedDatabase(self):
        pass


# ============================================================
# MainTestLinearTableAlgorithm.java style runner
# ============================================================

def main():
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextPasquier99.txt"
    output_path = script_dir / "output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextPasquier99.txt in the same folder as this Python file.")
        return

    minsup = 0.4

    algo = AlgoLinearTable()
    algo.runAlgorithm(str(input_path), str(output_path), minsup)
    algo.printStats()

    print("\nOutput saved to:", output_path.name)
    print("\nContents of output file:\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
