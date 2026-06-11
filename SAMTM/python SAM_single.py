#!/usr/bin/env python3
from __future__ import annotations

import math
import time
import tracemalloc
from pathlib import Path
from typing import Dict, List, Optional


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @staticmethod
    def getInstance():
        if MemoryLogger._instance is None:
            MemoryLogger._instance = MemoryLogger()
        return MemoryLogger._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        tracemalloc.start()

    def checkMemory(self):
        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        currentMemory = current / 1024.0 / 1024.0
        peakMemory = peak / 1024.0 / 1024.0
        if peakMemory > self.maxMemory:
            self.maxMemory = peakMemory
        return currentMemory


class ItemNameConverter:
    def __init__(self, itemCount: int, firstItemName: int = 1):
        self.newNamesToOldNames = [0] * (itemCount + firstItemName)
        self.oldNamesToNewNames: Dict[int, int] = {}
        self.currentIndex = firstItemName

    def assignNewName(self, oldName: int) -> int:
        newName = self.currentIndex
        self.oldNamesToNewNames[oldName] = newName
        self.newNamesToOldNames[newName] = oldName
        self.currentIndex += 1
        return newName

    def toNewName(self, oldName: int) -> int:
        return self.oldNamesToNewNames[oldName]

    def toOldName(self, newName: int) -> int:
        return self.newNamesToOldNames[newName]

    def isOldItemExisting(self, item: int) -> bool:
        return item in self.oldNamesToNewNames


class TransactionSAM:
    def __init__(self, items: List[int], offset: int, weight: int):
        self.items = items
        self.offset = offset
        self.weight = weight

    def copy(self):
        return TransactionSAM(self.items, self.offset, self.weight)

    def firstItem(self) -> int:
        return -1 if self.isEmpty() else self.items[self.offset]

    def removeFirst(self):
        self.offset += 1

    def isEmpty(self) -> bool:
        return self.offset >= len(self.items)

    def addWeight(self, additional: int):
        self.weight += additional

    def getWeight(self) -> int:
        return self.weight

    def getItem(self, index: int) -> int:
        pos = self.offset + index
        return self.items[pos] if pos < len(self.items) else -1

    def size(self) -> int:
        return len(self.items) - self.offset


class AlgoSAM:
    def __init__(self):
        self.minSupport = 0.0
        self.minSupportAbsolute = 0
        self.peakMemory = 0.0
        self.maxPatternLength = 2**31 - 1
        self.totalTime = 0
        self.itemsetCount = 0
        self.writer = None
        self.nameConverter: Optional[ItemNameConverter] = None
        self.frequentItemCount = 0
        self.itemsetBuffer: Optional[List[int]] = None
        self.parseBuffer = [0] * 1024

    def setMaximumPatternLength(self, maxLength: int):
        if maxLength < 1:
            raise ValueError("Maximum pattern length must be at least 1")
        self.maxPatternLength = maxLength

    def runAlgorithm(self, inputPath: str, outputPath: str, minSupport: float):
        self.totalTime = 0
        self.minSupport = minSupport
        self.itemsetCount = 0

        MemoryLogger.getInstance().reset()
        startTime = int(time.time() * 1000)

        preprocessed = self.readTransactions(inputPath)
        MemoryLogger.getInstance().checkMemory()

        if preprocessed:
            with open(outputPath, "w", encoding="utf-8") as bw:
                self.writer = bw
                bufferSize = min(self.frequentItemCount, self.maxPatternLength)
                self.itemsetBuffer = [0] * bufferSize

                transactions = list(preprocessed)
                MemoryLogger.getInstance().checkMemory()

                prefix = [0] * bufferSize
                self.sam(transactions, prefix, 0)

                MemoryLogger.getInstance().checkMemory()
        else:
            with open(outputPath, "w", encoding="utf-8"):
                pass

        self.peakMemory = MemoryLogger.getInstance().checkMemory()
        self.totalTime = int(time.time() * 1000) - startTime

    def readTransactions(self, inputPath: str) -> List[TransactionSAM]:
        itemCounts: Dict[int, int] = {}
        rawTransactions: List[List[int]] = []

        with open(inputPath, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if self.isCommentLine(line):
                    continue

                transaction = self.parseLine(line)
                if len(transaction) > 0:
                    rawTransactions.append(transaction)
                    for item in transaction:
                        itemCounts[item] = itemCounts.get(item, 0) + 1

        transactionCount = len(rawTransactions)
        self.minSupportAbsolute = max(1, int(math.ceil(self.minSupport * transactionCount)))

        frequentItems = []
        for item, count in itemCounts.items():
            if count >= self.minSupportAbsolute:
                frequentItems.append((item, count))

        frequentItems.sort(key=lambda e: e[1])
        self.frequentItemCount = len(frequentItems)

        if self.frequentItemCount == 0:
            self.nameConverter = ItemNameConverter(0, 0)
            return []

        self.nameConverter = ItemNameConverter(self.frequentItemCount, 0)
        for item, _count in frequentItems:
            self.nameConverter.assignNewName(item)

        transactions = self.recodeTransactions(rawTransactions)
        transactions = self.mergeIdenticalTransactions(transactions)
        return transactions

    def isCommentLine(self, line: str) -> bool:
        if line == "":
            return True
        first = line[0]
        return first == '#' or first == '%' or first == '@'

    def parseLine(self, line: str) -> List[int]:
        length = len(line)
        count = 0
        i = 0

        while i < length:
            while i < length and line[i] <= ' ':
                i += 1
            if i >= length:
                break

            negative = False
            if line[i] == '-':
                negative = True
                i += 1

            value = 0
            digitStart = i
            while i < length:
                c = line[i]
                if '0' <= c <= '9':
                    value = value * 10 + (ord(c) - 48)
                    i += 1
                else:
                    break

            if i > digitStart:
                if count >= len(self.parseBuffer):
                    self.parseBuffer.extend([0] * len(self.parseBuffer))
                self.parseBuffer[count] = -value if negative else value
                count += 1

            while i < length and line[i] > ' ':
                i += 1

        return self.parseBuffer[:count]

    def recodeTransactions(self, rawTransactions: List[List[int]]) -> List[TransactionSAM]:
        result: List[TransactionSAM] = []

        for raw in rawTransactions:
            count = 0
            for item in raw:
                if self.nameConverter.isOldItemExisting(item):
                    count += 1

            if count > 0:
                items = [0] * count
                index = 0
                for item in raw:
                    if self.nameConverter.isOldItemExisting(item):
                        items[index] = self.nameConverter.toNewName(item)
                        index += 1

                items.sort()
                result.append(TransactionSAM(items, 0, 1))

        result.sort(key=cmp_to_key(self.compareTransactions))
        return result

    def mergeIdenticalTransactions(self, transactions: List[TransactionSAM]) -> List[TransactionSAM]:
        if not transactions:
            return transactions

        combined: List[TransactionSAM] = []
        current = transactions[0]

        for i in range(1, len(transactions)):
            nxt = transactions[i]
            if self.compareTransactions(current, nxt) == 0:
                current.addWeight(nxt.getWeight())
            else:
                combined.append(current)
                current = nxt
        combined.append(current)
        return combined

    def sam(self, transactions: List[TransactionSAM], prefix: List[int], prefixLength: int):
        while transactions:
            currentItem = transactions[0].firstItem()

            projectedTransactions: List[TransactionSAM] = []
            support = 0

            while transactions and transactions[0].firstItem() == currentItem:
                transaction = transactions.pop(0)
                support += transaction.getWeight()
                transaction.removeFirst()

                if not transaction.isEmpty():
                    projectedTransactions.append(transaction)

            if support >= self.minSupportAbsolute:
                prefix[prefixLength] = currentItem
                self.writeItemset(prefix, prefixLength + 1, support)

                if prefixLength + 1 < self.maxPatternLength and projectedTransactions:
                    projectedCopy = [t.copy() for t in projectedTransactions]
                    self.sam(projectedCopy, prefix, prefixLength + 1)

            if not projectedTransactions:
                continue

            if not transactions:
                transactions = projectedTransactions
                continue

            mergedTransactions: List[TransactionSAM] = []
            i = 0
            j = 0
            while i < len(transactions) and j < len(projectedTransactions):
                compare = self.compareTransactions(transactions[i], projectedTransactions[j])

                if compare < 0:
                    mergedTransactions.append(transactions[i])
                    i += 1
                elif compare > 0:
                    mergedTransactions.append(projectedTransactions[j])
                    j += 1
                else:
                    merged = projectedTransactions[j]
                    merged.addWeight(transactions[i].getWeight())
                    mergedTransactions.append(merged)
                    i += 1
                    j += 1

            while i < len(transactions):
                mergedTransactions.append(transactions[i])
                i += 1
            while j < len(projectedTransactions):
                mergedTransactions.append(projectedTransactions[j])
                j += 1

            transactions = mergedTransactions

    def compareTransactions(self, a: TransactionSAM, b: TransactionSAM) -> int:
        index = 0
        while True:
            itemA = a.getItem(index)
            itemB = b.getItem(index)

            if itemA < 0:
                return 0 if itemB < 0 else 1
            if itemB < 0:
                return -1

            if itemA != itemB:
                return -1 if itemA < itemB else 1
            index += 1

    def writeItemset(self, itemset: List[int], length: int, support: int):
        self.itemsetCount += 1

        for i in range(length):
            self.itemsetBuffer[i] = self.nameConverter.toOldName(itemset[i])
        part = self.itemsetBuffer[:length]
        part.sort()

        line = " ".join(str(x) for x in part) + f" #SUP: {support}"
        self.writer.write(line + "\n")

    def printStats(self):
        print("============= SAM ALGORITHM 2.65 - STATS =============")
        if self.maxPatternLength != 2**31 - 1:
            print(" Max pattern length: " + str(self.maxPatternLength))
        print(" Frequent itemsets: " + str(self.itemsetCount))
        print(" Execution time: " + str(self.totalTime) + " ms")
        print(" Max memory: " + str(self.peakMemory) + " MB")
        print("==================================================")


def cmp_to_key(mycmp):
    class K:
        __slots__ = ['obj']
        def __init__(self, obj, *_):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K


def main():
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextPasquier99.txt"
    output_path = script_dir / "#SAM_Save_py.output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextPasquier99.txt in the same folder as this Python file.")
        return

    minSupport = 0.7
    algo = AlgoSAM()
    algo.runAlgorithm(str(input_path), str(output_path), minSupport)
    algo.printStats()

    print("\nOutput saved to:", output_path.name)
    print("\nContents of output file:\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
