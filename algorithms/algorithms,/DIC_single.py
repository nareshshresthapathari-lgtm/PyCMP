#!/usr/bin/env python3
from __future__ import annotations

import math
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class MemoryLogger:
    _instance: Optional["MemoryLogger"] = None

    def __init__(self) -> None:
        self.maxMemory = 0.0
        self.recordingMode = False
        self.outputFile: Optional[Path] = None
        self._writer = None

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
        if self.recordingMode and self._writer is not None:
            self._writer.write(f"{current_mb}\n")
            self._writer.flush()
        return current_mb

    def startRecordingMode(self, fileName: str) -> None:
        self.recordingMode = True
        self.outputFile = Path(fileName)
        self._writer = self.outputFile.open("w", encoding="utf-8")

    def stopRecordingMode(self) -> None:
        if self.recordingMode and self._writer is not None:
            self._writer.close()
            self._writer = None
            self.recordingMode = False


class AlgoDIC:
    DEFAULT_BUCKET_SIZE = 200

    class State:
        DASHED_BOX = "DASHED_BOX"
        SOLID_BOX = "SOLID_BOX"
        DASHED_CIRCLE = "DASHED_CIRCLE"
        SOLID_CIRCLE = "SOLID_CIRCLE"

    @dataclass
    class ItemsetData:
        state: str
        startBucket: int
        count: int = 0
        bucketsProcessed: int = 0

    @dataclass(frozen=True)
    class IntArrayWrapper:
        items: Tuple[int, ...]

        def __str__(self) -> str:
            return str(list(self.items))

    def __init__(self) -> None:
        self.startTimestamp = 0.0
        self.endTimestamp = 0.0
        self.itemsetCount = 0
        self.transactionCount = 0
        self.passCount = 0
        self.candidatesGenerated = 0
        self.maxMemory = 0.0

        self.minSupportAbsolute = 0
        self.bucketSize = self.DEFAULT_BUCKET_SIZE
        self.numBuckets = 0

        self.database: List[Tuple[int, ...]] = []
        self.allItems: List[int] = []

        self.itemsets: Dict[AlgoDIC.IntArrayWrapper, AlgoDIC.ItemsetData] = {}
        self.activeItemsets: Set[AlgoDIC.IntArrayWrapper] = set()
        self.pendingItemsets: Set[AlgoDIC.IntArrayWrapper] = set()
        self.frequentBySize: Dict[int, Set[AlgoDIC.IntArrayWrapper]] = {}
        self.subsetBuffer: List[int] = []

    def runAlgorithm(self, input_path: str, output_path: str, minSupport: float, bucketSize: Optional[int] = None) -> None:
        self.startTimestamp = time.time() * 1000.0
        self.itemsetCount = 0
        self.passCount = 0
        self.candidatesGenerated = 0
        self.maxMemory = 0.0
        MemoryLogger.getInstance().reset()

        self.bucketSize = bucketSize if bucketSize is not None else self.DEFAULT_BUCKET_SIZE

        self.itemsets = {}
        self.activeItemsets = set()
        self.pendingItemsets = set()
        self.frequentBySize = {}
        self.database = []

        self.readDatabase(input_path)

        if self.transactionCount == 0:
            self.writeOutput(output_path)
            self.endTimestamp = time.time() * 1000.0
            return

        if self.bucketSize > self.transactionCount:
            self.bucketSize = self.transactionCount

        self.numBuckets = (self.transactionCount + self.bucketSize - 1) // self.bucketSize
        self.minSupportAbsolute = int(math.ceil(minSupport * self.transactionCount))
        if self.minSupportAbsolute < 1:
            self.minSupportAbsolute = 1

        self.subsetBuffer = [0] * max(len(self.allItems), 1)

        self.runDIC()
        self.writeOutput(output_path)

        MemoryLogger.getInstance().checkMemory()
        self.maxMemory = MemoryLogger.getInstance().getMaxMemory()
        self.endTimestamp = time.time() * 1000.0

    def readDatabase(self, input_path: str) -> None:
        itemSet: Set[int] = set()

        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if not line:
                    continue
                if line[0] in "#%@":
                    continue

                parts = line.split()
                items: List[int] = []
                for part in parts:
                    try:
                        item = int(part)
                    except ValueError:
                        continue
                    items.append(item)
                    itemSet.add(item)

                if items:
                    transaction = tuple(sorted(items))
                    self.database.append(transaction)

        self.transactionCount = len(self.database)
        self.allItems = sorted(itemSet)

    def runDIC(self) -> None:
        if not self.allItems:
            return

        for item in self.allItems:
            itemset = (item,)
            key = self.IntArrayWrapper(itemset)
            self.itemsets[key] = self.ItemsetData(self.State.DASHED_BOX, 0)
            self.pendingItemsets.add(key)
            self.candidatesGenerated += 1

        absoluteBucketCount = 0
        currentBucket = 0

        while self.activeItemsets or self.pendingItemsets:
            self.promoteReadyItemsets(currentBucket)
            self.processBucket(currentBucket)
            newlyFrequent = self.checkForFrequentItemsets()

            if newlyFrequent:
                nextBucket = (currentBucket + 1) % self.numBuckets
                self.generateCandidates(newlyFrequent, nextBucket)

            absoluteBucketCount += 1
            currentBucket = (currentBucket + 1) % self.numBuckets

            if absoluteBucketCount > 0 and absoluteBucketCount % self.numBuckets == 0:
                self.passCount += 1

            MemoryLogger.getInstance().checkMemory()

    def processBucket(self, bucketIndex: int) -> None:
        startTid = bucketIndex * self.bucketSize
        endTid = min(startTid + self.bucketSize, self.transactionCount)

        if not self.activeItemsets:
            return

        for tid in range(startTid, endTid):
            transaction = self.database[tid]
            for key in list(self.activeItemsets):
                data = self.itemsets[key]
                if self.transactionContains(transaction, key.items):
                    data.count += 1

        for key in list(self.activeItemsets):
            self.itemsets[key].bucketsProcessed += 1

    def promoteReadyItemsets(self, currentBucket: int) -> None:
        to_promote = []
        for key in self.pendingItemsets:
            data = self.itemsets[key]
            if data.startBucket == currentBucket:
                to_promote.append(key)

        for key in to_promote:
            data = self.itemsets[key]
            data.state = self.State.SOLID_BOX
            data.bucketsProcessed = 0
            self.activeItemsets.add(key)
            self.pendingItemsets.remove(key)

    def checkForFrequentItemsets(self) -> List["AlgoDIC.IntArrayWrapper"]:
        newlyFrequent: List[AlgoDIC.IntArrayWrapper] = []
        to_remove = []

        for key in list(self.activeItemsets):
            data = self.itemsets[key]
            if data.bucketsProcessed >= self.numBuckets:
                if data.count >= self.minSupportAbsolute:
                    data.state = self.State.SOLID_CIRCLE
                    newlyFrequent.append(key)
                    self.addToFrequentBySize(key)
                else:
                    data.state = self.State.DASHED_CIRCLE
                to_remove.append(key)

        for key in to_remove:
            self.activeItemsets.remove(key)

        return newlyFrequent

    def generateCandidates(self, newlyFrequent: List["AlgoDIC.IntArrayWrapper"], startBucket: int) -> None:
        newBySize: Dict[int, List[Tuple[int, ...]]] = {}
        for wrapper in newlyFrequent:
            size = len(wrapper.items)
            newBySize.setdefault(size, []).append(wrapper.items)

        for _, newFreqK in newBySize.items():
            if len(newFreqK) < 2:
                continue

            sortedNew = sorted(newFreqK)
            for i in range(len(sortedNew)):
                for j in range(i + 1, len(sortedNew)):
                    itemset1 = sortedNew[i]
                    itemset2 = sortedNew[j]

                    if not self.sharePrefix(itemset1, itemset2):
                        continue

                    candidate = self.joinItemsets(itemset1, itemset2)
                    if candidate is None:
                        continue

                    candidateKey = self.IntArrayWrapper(candidate)

                    if candidateKey in self.itemsets:
                        continue
                    if not self.allSubsetsFrequent(candidate):
                        continue

                    self.itemsets[candidateKey] = self.ItemsetData(self.State.DASHED_BOX, startBucket)
                    self.pendingItemsets.add(candidateKey)
                    self.candidatesGenerated += 1

    def sharePrefix(self, a: Tuple[int, ...], b: Tuple[int, ...]) -> bool:
        if len(a) != len(b):
            return False
        for i in range(len(a) - 1):
            if a[i] != b[i]:
                return False
        return True

    def joinItemsets(self, a: Tuple[int, ...], b: Tuple[int, ...]) -> Optional[Tuple[int, ...]]:
        k = len(a)
        lastA = a[k - 1]
        lastB = b[k - 1]
        if lastA >= lastB:
            return None
        return a + (lastB,)

    def allSubsetsFrequent(self, itemset: Tuple[int, ...]) -> bool:
        if len(itemset) <= 1:
            return True

        subsetSize = len(itemset) - 1
        for skip in range(len(itemset)):
            idx = 0
            for i in range(len(itemset)):
                if i != skip:
                    self.subsetBuffer[idx] = itemset[i]
                    idx += 1

            subset = tuple(self.subsetBuffer[:subsetSize])
            subsetKey = self.IntArrayWrapper(subset)
            subsetData = self.itemsets.get(subsetKey)

            if subsetData is None or subsetData.state != self.State.SOLID_CIRCLE:
                return False
        return True

    def addToFrequentBySize(self, key: "AlgoDIC.IntArrayWrapper") -> None:
        size = len(key.items)
        self.frequentBySize.setdefault(size, set()).add(key)

    def transactionContains(self, transaction: Tuple[int, ...], itemset: Tuple[int, ...]) -> bool:
        if len(itemset) > len(transaction):
            return False

        ti = 0
        ii = 0
        while ii < len(itemset) and ti < len(transaction):
            if transaction[ti] == itemset[ii]:
                ti += 1
                ii += 1
            elif transaction[ti] < itemset[ii]:
                ti += 1
            else:
                return False
        return ii == len(itemset)

    def writeOutput(self, output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as writer:
            for key, data in self.itemsets.items():
                if data.state == self.State.SOLID_CIRCLE:
                    self.itemsetCount += 1
                    line = " ".join(str(x) for x in key.items) + f" #SUP: {data.count}"
                    writer.write(line + "\n")

    def printStats(self) -> None:
        print("====== DIC ALGORITHM - STATS ======")
        print(f" Transactions: {self.transactionCount}")
        print(f" Unique items: {len(self.allItems) if self.allItems is not None else 0}")
        print(f" Bucket size (M): {self.bucketSize}")
        print(f" Number of buckets: {self.numBuckets}")
        print(f" Candidates generated: {self.candidatesGenerated}")
        print(f" Database passes: {self.passCount}")
        print()
        print(f" Frequent itemsets: {self.itemsetCount}")
        print(f" Time: {int(self.endTimestamp - self.startTimestamp)} ms")
        print(f" Memory: {self.maxMemory:.2f} MB")
        print("===================================")


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextPasquier99.txt"
    output_path = script_dir / "output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextPasquier99.txt in the same folder as this Python file.")
        return

    minSupport = 0.4
    intervalSize = 2

    algorithm = AlgoDIC()
    algorithm.runAlgorithm(str(input_path), str(output_path), minSupport, intervalSize)
    algorithm.printStats()

    print(f"\nOutput saved to: {output_path.name}\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
