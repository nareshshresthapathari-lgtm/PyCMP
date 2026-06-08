#!/usr/bin/env python3
from __future__ import annotations

import math
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


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
        peak_mb = peak / 1024.0 / 1024.0
        if peak_mb > self.maxMemory:
            self.maxMemory = peak_mb
        return current / 1024.0 / 1024.0


# ============================================================
# AbstractItemset.java / AbstractOrderedItemset.java
# ============================================================

class AbstractItemset:
    def size(self) -> int:
        raise NotImplementedError

    def getAbsoluteSupport(self) -> int:
        raise NotImplementedError

    def getRelativeSupport(self, nbObject: int) -> float:
        raise NotImplementedError

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

    def getRelativeSupport(self, nbObject: int) -> float:
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            gi = self.get(i)
            if gi == item:
                return True
            elif gi > item:
                return False
        return False

    def containsAll(self, itemset2: "AbstractOrderedItemset") -> bool:
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

    def isEqualTo(self, other) -> bool:
        if isinstance(other, AbstractOrderedItemset):
            if self.size() != other.size():
                return False
            for i in range(other.size()):
                if other.get(i) != self.get(i):
                    return False
            return True
        else:
            arr = other
            if self.size() != len(arr):
                return False
            for i, v in enumerate(arr):
                if self.get(i) != v:
                    return False
            return True

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
# Itemset.java
# ============================================================

@dataclass(eq=False)
class Itemset(AbstractOrderedItemset):
    itemset: List[int] = field(default_factory=list)
    support: int = 0

    def __init__(self, items=None, support: int = 0):
        if items is None:
            self.itemset = []
        elif isinstance(items, int):
            self.itemset = [items]
        else:
            self.itemset = list(items)
        self.support = support

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
        newItemset = [x for x in self.itemset if x != itemToRemove]
        return Itemset(newItemset)

    def cloneItemSetMinusAnItemset(self, itemsetToNotKeep: "Itemset") -> "Itemset":
        newItemset = [x for x in self.itemset if not itemsetToNotKeep.contains(x)]
        return Itemset(newItemset)

    def intersection(self, itemset2: "Itemset") -> "Itemset":
        inter = ArraysAlgos.intersectTwoSortedArrays(self.getItems(), itemset2.getItems())
        return Itemset(inter)

    def __hash__(self) -> int:
        return hash(tuple(self.itemset))

    def __eq__(self, other) -> bool:
        return isinstance(other, Itemset) and self.itemset == other.itemset


# ============================================================
# Zart table classes
# ============================================================

class TCTableCandidate:
    def __init__(self) -> None:
        self.levels: List[List[Itemset]] = []
        self.mapPredSupp: Dict[Itemset, int] = {}
        self.mapKey: Dict[Itemset, bool] = {}

    def thereisARowKeyValueIsTrue(self, i: int) -> bool:
        for c in self.levels[i]:
            if self.mapKey.get(c) is True:
                return True
        return False


class TFTableFrequent:
    def __init__(self) -> None:
        self.levels: List[List[Itemset]] = []
        self.mapPredSupp: Dict[Itemset, int] = {}
        self.mapKey: Dict[Itemset, bool] = {}
        self.mapClosed: Dict[Itemset, bool] = {}
        self.emptySetIsClosed = False

    def addFrequentItemset(self, itemset: Itemset) -> None:
        while len(self.levels) <= itemset.size():
            self.levels.append([])
        self.levels[itemset.size()].append(itemset)

    def getLevelForZart(self, i: int) -> List[Itemset]:
        if i + 1 == len(self.levels):
            newList: List[Itemset] = []
            self.levels.append(newList)
            return newList
        return self.levels[i + 1]


class TZTableClosed:
    def __init__(self) -> None:
        self.levels: List[List[Itemset]] = []
        self.mapGenerators: Dict[Itemset, List[Itemset]] = {}

    def addClosedItemset(self, itemset: Itemset) -> None:
        while len(self.levels) <= itemset.size():
            self.levels.append([])
        self.levels[itemset.size()].append(itemset)

    def getLevelForZart(self, i: int) -> List[Itemset]:
        if i + 1 == len(self.levels):
            newList: List[Itemset] = []
            self.levels.append(newList)
            return newList
        return self.levels[i + 1]


# ============================================================
# Rules.java
# ============================================================

@dataclass
class Rule:
    itemset1: List[int]
    itemset2: List[int]
    coverage: int
    transactionCount: int
    confidence: float

    def getRelativeSupport(self, databaseSize: int) -> float:
        return float(self.transactionCount) / float(databaseSize)

    def getAbsoluteSupport(self) -> int:
        return self.transactionCount

    def getConfidence(self) -> float:
        return self.confidence

    def getCoverage(self) -> int:
        return self.coverage

    def print(self) -> None:
        print(self.toString())

    def toString(self) -> str:
        buffer = []
        for i, v in enumerate(self.itemset1):
            buffer.append(str(v))
            if i != len(self.itemset1) - 1:
                buffer.append(" ")
        buffer.append(" ==> ")
        for i, v in enumerate(self.itemset2):
            buffer.append(str(v))
            buffer.append(" ")
        return "".join(buffer)

    def getItemset1(self) -> List[int]:
        return self.itemset1

    def getItemset2(self) -> List[int]:
        return self.itemset2


class Rules:
    def __init__(self, name: str):
        self.rules: List[Rule] = []
        self.name = name

    def sortByConfidence(self) -> None:
        self.rules.sort(key=lambda r: r.getConfidence(), reverse=True)

    def printRules(self, databaseSize: int) -> None:
        print(" ------- " + self.name + " -------")
        i = 0
        for rule in self.rules:
            print("  rule " + str(i) + ":  " + rule.toString() +
                  "support :  " + str(rule.getRelativeSupport(databaseSize)) +
                  " (" + str(rule.getAbsoluteSupport()) + "/" + str(databaseSize) + ") " +
                  "confidence :  " + str(rule.getConfidence()))
            i += 1
        print(" --------------------------------")

    def addRule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def getRulesCount(self) -> int:
        return len(self.rules)

    def getRules(self) -> List[Rule]:
        return self.rules


# ============================================================
# TransactionDatabase.java
# ============================================================

class TransactionDatabase:
    def __init__(self) -> None:
        self.items: Set[int] = set()
        self.transactions: List[List[int]] = []
        self.maxItemID = 0
        self.mapItemIDtoStringValue: Optional[Dict[int, str]] = None

    def addTransaction(self, transaction: List[int]) -> None:
        self.transactions.append(transaction)
        self.items.update(transaction)

    def loadFile(self, path: str) -> None:
        self.maxItemID = 0
        with open(path, "r", encoding="utf-8") as myInput:
            for thisLine in myInput:
                thisLine = thisLine.rstrip("\n")
                if not thisLine:
                    continue
                if thisLine.startswith("@ITEM"):
                    thisLine = thisLine[6:]
                    index = thisLine.index("=")
                    itemID = int(thisLine[:index])
                    stringValue = thisLine[index + 1:]
                    if self.mapItemIDtoStringValue is None:
                        self.mapItemIDtoStringValue = {}
                    self.mapItemIDtoStringValue[itemID] = stringValue
                elif thisLine[0] not in "#%@":
                    self._addTransactionFromStrings(thisLine.split(" "))

    def _addTransactionFromStrings(self, itemsString: List[str]) -> None:
        itemset: List[int] = []
        for attribute in itemsString:
            item = int(attribute)
            itemset.append(item)
            self.items.add(item)
            if item > self.maxItemID:
                self.maxItemID = item
        self.transactions.append(itemset)

    def size(self) -> int:
        return len(self.transactions)

    def getTransactions(self) -> List[List[int]]:
        return self.transactions

    def getItems(self) -> Set[int]:
        return self.items

    def getNameForItem(self, item: int) -> Optional[str]:
        if self.mapItemIDtoStringValue is None:
            return None
        return self.mapItemIDtoStringValue.get(item)

    def getMapItemToStringValues(self):
        return self.mapItemIDtoStringValue

    def getMaxItemID(self) -> int:
        return self.maxItemID


# ============================================================
# AlgoZart.java
# ============================================================

class AlgoZart:
    def __init__(self):
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.minsupRelative = 0
        self.context: Optional[TransactionDatabase] = None
        self.tableClosed: Optional[TZTableClosed] = None
        self.tableFrequent: Optional[TFTableFrequent] = None
        self.tableCandidate: Optional[TCTableCandidate] = None
        self.frequentGeneratorsFG: Optional[List[Itemset]] = None

    def runAlgorithm(self, database: TransactionDatabase, minsupp: float) -> TZTableClosed:
        self.startTimestamp = int(time.time() * 1000)
        MemoryLogger.getInstance().reset()

        self.context = database
        self.frequentGeneratorsFG = []
        self.tableClosed = TZTableClosed()
        self.tableFrequent = TFTableFrequent()
        self.tableCandidate = TCTableCandidate()

        self.minsupRelative = int(math.ceil(minsupp * database.size()))

        mapItemSupport: Dict[int, int] = {}
        for transaction in database.getTransactions():
            for item in transaction:
                mapItemSupport[item] = mapItemSupport.get(item, 0) + 1

        for transaction in database.getTransactions():
            transaction[:] = [item for item in transaction if mapItemSupport[item] >= self.minsupRelative]

        self.tableCandidate.levels.append([])
        for item in mapItemSupport.keys():
            itemset = Itemset(item)
            itemset.setAbsoluteSupport(mapItemSupport[item])
            if mapItemSupport[item] >= self.minsupRelative:
                self.tableFrequent.addFrequentItemset(itemset)
                self.tableCandidate.levels[0].append(itemset)

        if len(self.tableFrequent.levels) != 0:
            fullCollumn = False

            for l in self.tableFrequent.getLevelForZart(0):
                self.tableFrequent.mapClosed[l] = True
                if l.getAbsoluteSupport() == len(database.getTransactions()):
                    self.tableFrequent.mapKey[l] = False
                    fullCollumn = True
                else:
                    self.tableFrequent.mapKey[l] = True

            emptyset = Itemset([])
            if fullCollumn:
                self.frequentGeneratorsFG.append(emptyset)
            else:
                self.tableFrequent.addFrequentItemset(emptyset)
                self.tableFrequent.mapClosed[emptyset] = True
                self.tableFrequent.mapPredSupp[emptyset] = database.size()
                self.tableClosed.addClosedItemset(emptyset)
                self.tableClosed.mapGenerators[emptyset] = []
                emptyset.setAbsoluteSupport(database.size())

            i = 1
            while True:
                self.zartGen(i)
                if len(self.tableCandidate.levels[i]) == 0:
                    break

                if self.tableCandidate.thereisARowKeyValueIsTrue(i):
                    for o in database.getTransactions():
                        for s in self.subset_list_itemset(self.tableCandidate.levels[i], o):
                            if self.tableCandidate.mapKey.get(s):
                                s.increaseTransactionCount()

                for c in self.tableCandidate.levels[i]:
                    if c.getAbsoluteSupport() >= self.minsupRelative:
                        if self.tableCandidate.mapKey.get(c) is True and c.getAbsoluteSupport() == self.tableCandidate.mapPredSupp.get(c):
                            self.tableCandidate.mapKey[c] = False
                        self.tableFrequent.addFrequentItemset(c)
                        self.tableFrequent.mapKey[c] = self.tableCandidate.mapKey.get(c)
                        self.tableFrequent.mapPredSupp[c] = self.tableCandidate.mapPredSupp.get(c)

                for l in self.tableFrequent.getLevelForZart(i):
                    self.tableFrequent.mapClosed[l] = True
                    for s in self.subset_list_itemset_obj(self.tableFrequent.getLevelForZart(i - 1), l):
                        if s.getAbsoluteSupport() == l.getAbsoluteSupport():
                            self.tableFrequent.mapClosed[s] = False

                self.tableClosed.levels.append([])
                for l in self.tableFrequent.getLevelForZart(i - 1):
                    if self.tableFrequent.mapClosed.get(l) is True:
                        self.tableClosed.getLevelForZart(i - 1).append(l)

                self.findGenerators(self.tableClosed.getLevelForZart(i - 1), i)
                MemoryLogger.getInstance().checkMemory()
                i += 1

            self.tableClosed.levels.append([])
            for l in self.tableFrequent.getLevelForZart(i - 1):
                self.tableClosed.getLevelForZart(i - 1).append(l)

            self.findGenerators(self.tableClosed.getLevelForZart(i - 1), i)

        MemoryLogger.getInstance().checkMemory()
        self.endTimestamp = int(time.time() * 1000)
        return self.tableClosed

    def findGenerators(self, zi: List[Itemset], i: int) -> None:
        for z in zi:
            s = self.subset_list_itemset_obj(self.frequentGeneratorsFG, z)
            self.tableClosed.mapGenerators[z] = s
            for x in s:
                if x in self.frequentGeneratorsFG:
                    self.frequentGeneratorsFG.remove(x)
        for l in self.tableFrequent.getLevelForZart(i - 1):
            if self.tableFrequent.mapKey.get(l) is True and self.tableFrequent.mapClosed.get(l) is False:
                self.frequentGeneratorsFG.append(l)

    def subset_list_itemset_obj(self, s: List[Itemset], l: Itemset) -> List[Itemset]:
        retour = []
        for itemsetS in s:
            allIncluded = True
            for i in range(itemsetS.size()):
                if not l.contains(itemsetS.get(i)):
                    allIncluded = False
            if allIncluded:
                retour.append(itemsetS)
        return retour

    def subset_list_itemset(self, s: List[Itemset], l: List[int]) -> List[Itemset]:
        subset = []
        for itemsetS in s:
            allIncluded = True
            for i in range(itemsetS.size()):
                if itemsetS.get(i) not in l:
                    allIncluded = False
            if allIncluded:
                subset.append(itemsetS)
        return subset

    def zartGen(self, i: int) -> None:
        self.prepareCandidateSizeI(i)
        for c in list(self.tableCandidate.levels[i]):
            self.tableCandidate.mapKey[c] = True
            self.tableCandidate.mapPredSupp[c] = len(self.context.getTransactions()) + 1

            for j in range(c.size()):
                s = c.cloneItemSetMinusOneItem(c.get(j))
                found = False
                for itemset2 in self.tableFrequent.getLevelForZart(i - 1):
                    if itemset2.isEqualTo(s):
                        found = True
                        break
                if not found:
                    self.tableCandidate.levels[i].remove(c)
                    break
                else:
                    occurenceS = self.getPreviousOccurenceOfItemset(s, self.tableCandidate.levels[i - 1])
                    if occurenceS.getAbsoluteSupport() < self.tableCandidate.mapPredSupp[c]:
                        self.tableCandidate.mapPredSupp[c] = occurenceS.getAbsoluteSupport()
                    else:
                        self.tableCandidate.mapPredSupp[c] = self.tableCandidate.mapPredSupp[c]
                    if self.tableFrequent.mapKey.get(occurenceS) is False:
                        self.tableCandidate.mapKey[c] = False

            if c in self.tableCandidate.mapKey and self.tableCandidate.mapKey[c] is False:
                c.setAbsoluteSupport(self.tableCandidate.mapPredSupp[c])

    def getPreviousOccurenceOfItemset(self, itemset: Itemset, lst: List[Itemset]) -> Optional[Itemset]:
        for itemset2 in lst:
            if itemset2.isEqualTo(itemset):
                return itemset2
        return None

    def prepareCandidateSizeI(self, size: int) -> None:
        self.tableCandidate.levels.append([])
        for itemset1 in self.tableFrequent.getLevelForZart(size - 1):
            for itemset2 in self.tableFrequent.getLevelForZart(size - 1):
                missing = itemset2.allTheSameExceptLastItem(itemset1)
                if missing is not None:
                    union = [0] * (itemset1.size() + 1)
                    union[:itemset2.size()] = itemset2.itemset[:]
                    union[itemset2.size()] = missing
                    self.tableCandidate.levels[size].append(Itemset(union))

    def getTableFrequent(self) -> TFTableFrequent:
        return self.tableFrequent

    def printStatistics(self) -> None:
        print("========== ZART - STATS ============")
        print(" Total time ~: " + str(self.endTimestamp - self.startTimestamp) + " ms")
        print(" Max memory:" + str(MemoryLogger.getInstance().getMaxMemory()))
        print("=====================================")


# ============================================================
# AlgoIGB.java
# ============================================================

class AlgoIGB:
    def __init__(self):
        self.closedPatternsAndGenerators: Optional[TZTableClosed] = None
        self.minconf = 0.0
        self.databaseSize = 0
        self.rules: Optional[Rules] = None
        self.startTimestamp = 0
        self.endTimeStamp = 0
        self.ruleCount = 0
        self.writer = None

    def runAlgorithm(self, closedPatternsAndGenerators: TZTableClosed, databaseSize: int, minconf: float, outputFilePath: Optional[str]):
        if outputFilePath is None:
            self.writer = None
            self.rules = Rules("IGB ASSOCIATION RULES")
        else:
            self.rules = None
            self.writer = open(outputFilePath, "w", encoding="utf-8")

        self.startTimestamp = int(time.time() * 1000)
        self.minconf = minconf
        self.closedPatternsAndGenerators = closedPatternsAndGenerators
        self.databaseSize = databaseSize
        self.ruleCount = 0

        for level in closedPatternsAndGenerators.levels:
            for itemset in level:
                if itemset.size() != 0:
                    self.processItemset(itemset)

        self.endTimeStamp = int(time.time() * 1000)
        if self.writer is not None:
            self.writer.close()
        return self.rules

    def processItemset(self, i: Itemset) -> None:
        if i.getRelativeSupport(self.databaseSize) >= self.minconf:
            self.save(Itemset(), i, i.getAbsoluteSupport(), i.getRelativeSupport(self.databaseSize))
            return

        lSmallestPremise: Set[Itemset] = set()

        for j in range(i.size()):
            for i1 in self.closedPatternsAndGenerators.levels[j]:
                if (float(i.getAbsoluteSupport()) / float(i1.getAbsoluteSupport())) >= self.minconf and i.containsAll(i1):
                    for genI1 in self.closedPatternsAndGenerators.mapGenerators.get(i1, []):
                        thereIsSmaller = False
                        for l in lSmallestPremise:
                            if genI1.containsAll(l) and genI1.size() != l.size():
                                thereIsSmaller = True
                                break
                        if thereIsSmaller is False:
                            lSmallestPremise.add(genI1)

        for gs in lSmallestPremise:
            list_i_gs = []
            for item in i.itemset:
                if not gs.contains(item):
                    list_i_gs.append(item)
            temp = [0] * len(list_i_gs)
            for k in range(len(list_i_gs)):
                temp[k] = list_i_gs[k]
            i_gs = Itemset(temp)
            self.save(gs, i_gs, i.getAbsoluteSupport(),
                      float(i.getAbsoluteSupport()) / float(gs.getAbsoluteSupport()))

    def save(self, itemset1: Itemset, itemset2: Itemset, absoluteSupport: int, confidence: float) -> None:
        self.ruleCount += 1
        if self.writer is not None:
            buffer = []
            if itemset1.size() == 0:
                buffer.append("__")
            else:
                for i in range(itemset1.size()):
                    buffer.append(str(itemset1.get(i)))
                    if i != itemset1.size() - 1:
                        buffer.append(" ")
            buffer.append(" ==> ")
            for i in range(itemset2.size()):
                buffer.append(str(itemset2.get(i)))
                if i != itemset2.size() - 1:
                    buffer.append(" ")
            buffer.append(" #SUP: ")
            buffer.append(str(absoluteSupport))
            buffer.append(" #CONF: ")
            buffer.append(str(confidence))
            self.writer.write("".join(buffer) + "\n")
        else:
            rule = Rule(itemset1.getItems(), itemset2.getItems(), itemset1.support, absoluteSupport, confidence)
            self.rules.addRule(rule)

    def printStatistics(self) -> None:
        print("============= IGB ASSOCIATION RULE GENERATION - STATS =============")
        print(" Number of association rules generated : " + str(self.ruleCount))
        print(" Total time ~ " + str(self.endTimeStamp - self.startTimestamp) + " ms")
        print("===================================================")


# ============================================================
# MainTestIGB_saveToMemory.java style runner
# ============================================================

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextIGB.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextIGB.txt in the same folder as this Python file.")
        return

    print("STEP 1 : EXECUTING THE ZART ALGORITHM TO FIND CLOSED ITEMSETS AND MINIMUM GENERATORS")
    database = TransactionDatabase()
    database.loadFile(str(input_path))

    zart = AlgoZart()
    minsup = 0.5
    results = zart.runAlgorithm(database, minsup)
    zart.printStatistics()

    print("STEP 2 : RUNNING THE IGB ALGORITHM")
    minconf = 0.61
    algoIGB = AlgoIGB()
    rules = algoIGB.runAlgorithm(results, len(database.getTransactions()), minconf, None)
    algoIGB.printStatistics()
    rules.printRules(len(database.getTransactions()))


if __name__ == "__main__":
    main()
