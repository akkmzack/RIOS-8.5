## Copyright 2009, Riverbed Technology, Inc., All rights reserved.
##
## Support for report graphics.
## Ripped out of products/rbt_*/support_reports and refactored to eliminate duplicate code
##
## Author: David Scott

import time
import ttime
import re
import xml.dom
import stats
import gfxgen

import OSUtils
import GfxUtils
import ReportUtils
import Logging
import Mgmt
import Nodes
from GfxContent import GfxContent
from ProductReportContext import ProductGfxContext
import ReportGenerationHelper
import RVBDUtils

class gfx_Report(GfxContent):

    dispatchList = ['bandwidthOptimization',
                    'bandwidthSummary',
                    'branchWarmingShared',
                    'branchWarmingWanVsWarm',
                    'connectionHistorySummary',
                    'connectionHistoryOptimized',
                    'connectionPool',
                    'cpuUtil',
                    'csaThroughputFrontEndIn',
                    'csaThroughputFrontEndOut',
                    'csaThroughputBackEndIn',
                    'csaThroughputBackEndOut',
                    'csaEvictionBytes',
                    'csaEvictionAge',
                    'csaBytesPending',
                    'csaDiskThroughput',
                    'csaDiskIOPS',
                    'csaDiskPercUtil',
                    'csaDiskAqsz',
                    'csaDiskAwait',
                    'csaDiskSvctm',
                    'dataReduction',
                    'dataStoreStatus',
                    'dataStoreClusterReads',
                    'dataStoreClusterWrites',
                    'dataStoreCompression',
                    'dataStoreEfficiency',
                    'dataStoreHits',
                    'dataStoreLoad',
                    'dataStorePageReads',
                    'dataStorePageWrites',
                    'dedupeFactor',
                    'dnsHits',
                    'dnsUtilBytes',
                    'dnsUtilEntries',
                    'endpointHistory',
                    'evaInitiatorStatsIO',
                    'evaInitiatorStatsIOPS',
                    'evaInitiatorStatsLatency',
                    'evaLunStatsIO',
                    'evaLunStatsIOPS',
                    'evaLunStatsLatency',
                    'evaBlockstoreStatsHitMiss',
                    'evaBlockstoreStatsUncmtd',
                    'evaBlockstoreStatsCommitDelay',
                    'evaBlockstoreStatsCommitIO',
                    'evaNetworkStats',
                    'httpPrefetchPerf',
                    'httpPrefetchPerfCombined',
                    'hypervisorCpu',
                    'hypervisorMemory',
                    'memoryPaging',
                    'neighborData',
                    'nfsCalls',
                    'pfsData',
                    'rspVNIIO',
                    'rsp3Vni',
                    'rsp3VmCpuUtil',
                    'rsp3VmMemory',
                    'rsp3VmDiskOps',
                    'rsp3VmDiskTput',
                    'qosClassesEnforced',
                    'qosClassesPreEnforcement',
                    'qosInboundClassesEnforced',
                    'qosInboundClassesPreEnforcement',
                    'srdfOverviewLan',
                    'srdfOverviewWan',
                    'srdfOverviewDataReduction',
                    'srdfServerDetailLan',
                    'srdfServerDetailWan',
                    'srdfServerDetailDataReduction',
                    'srdfGroupDetailThroughput',
                    'srdfGroupDetailDataReduction',
                    'sslConnectionRate',
                    'sslConnectionRequests',
                    'sslOptimization',
                    'tcpMemoryConsumption',
                    'tcpMemoryPressure',
                    'throughputLan',
                    'throughputWan',
                    'trafficSummary']

    # Get bandwidth optimization stats.
    # Save the stats in the session variable for later use in the
    # tabular and slider parts of the report.
    # Produce graphics for mime type graphics/jpg.
    def bandwidthOptimization(self):
        gg, doc = ReportGenerationHelper.bandwidthOptimization(self.mgmt,
                                                               self.fields,
                                                               ProductGfxContext)
        self.render(gg, 'Bandwidth Optimization')
        self.saveTabularInfo(doc)

    # ---*---

    def branchWarmingShared(self):
        gg, doc = ReportGenerationHelper.branchWarmingShared(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext)
        self.render(gg, 'Branch Warming')
        self.saveTabularInfo(doc)

    # ---*---

    def branchWarmingWanVsWarm(self):
        gg, doc = ReportGenerationHelper.branchWarmingWanVsWarm(self.mgmt,
                                                                self.fields,
                                                                ProductGfxContext)
        self.render(gg, 'Branch Warming')
        self.saveTabularInfo(doc)

    # ---*---

    def connectionHistoryOptimized(self):
        gg, doc = ReportGenerationHelper.connectionHistoryOptimized(self.mgmt,
                                                                    self.fields,
                                                                    ProductGfxContext)
        self.render(gg, 'Optimized Connections')
        self.saveTabularInfo(doc)

    # ---*---
    def connectionHistorySummary(self):
        gg, doc = ReportGenerationHelper.connectionHistorySummary(self.mgmt,
                                                                  self.fields,
                                                                  ProductGfxContext)
        self.render(gg, 'Optimized vs Pass Through Connections')
        self.saveTabularInfo(doc)

    # ---*---

    def connectionPool(self):
        gg, doc = ReportGenerationHelper.connectionPool(self.mgmt,
                                                        self.fields,
                                                        ProductGfxContext)
        self.render(gg, 'Connection Pool Hits')
        self.saveTabularInfo(doc)

    # ---*---

    def cpuUtil(self):
        gg, doc = ReportGenerationHelper.cpuUtil(self.mgmt,
                                                 self.fields,
                                                 ProductGfxContext)
        self.render(gg, 'CPU Utilization')
        self.saveTabularInfo(doc)

    # ---*---

    def dataReduction(self):
        gg, doc = ReportGenerationHelper.dataReduction(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'Data Reduction')
        self.saveTabularInfo(doc)

    # ---*---

    def dataStoreStatus(self):
        gg, doc = ReportGenerationHelper.dataStoreStatus(self.mgmt,
                                                     self.fields,
                                                     ProductGfxContext)
        self.saveTabularInfo(doc)

    # ---*---

    def dataStoreClusterReads(self):
        gg, doc = ReportGenerationHelper.dataStoreClusterReads(self.mgmt,
                                                               self.fields,
                                                               ProductGfxContext)
        self.render(gg, 'Data Store Cluster Average Reads Per Second')
        self.saveTabularInfo(doc)

    # ---*---

    def dataStoreClusterWrites(self):
        (gg, doc) = ReportGenerationHelper.dataStoreClusterWrites(self.mgmt,
                                                                  self.fields,
                                                                  ProductGfxContext)
        self.render(gg, 'Data Store Cluster Average Writes Per Second')

    # ---*---

    def dataStorePageReads(self):
        gg, doc = ReportGenerationHelper.dataStorePageReads(self.mgmt,
                                                            self.fields,
                                                            ProductGfxContext)
        self.render(gg, 'Data Store Page Reads Per Second')
        self.saveTabularInfo(doc)

    def dataStorePageWrites(self):
        gg, doc = ReportGenerationHelper.dataStorePageWrites(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext)
        self.render(gg, 'Data Store Page Writes Per Second')

    # ---*---

    def dataStoreCompression(self):
        gg, doc = ReportGenerationHelper.dataStoreCompression(self.mgmt,
                                                              self.fields,
                                                              ProductGfxContext)
        self.render(gg, 'Data Store SDR-Adaptive Compression')
        self.saveTabularInfo(doc)

    # ---*---

    def dataStoreEfficiency(self):
        gg, doc = ReportGenerationHelper.dataStoreEfficiency(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext)
        self.render(gg, 'Data Store Read Efficiency')
        self.saveTabularInfo(doc)

    # ---*---

    def dataStoreHits(self):
        gg, doc = ReportGenerationHelper.dataStoreHits(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'Data Store Hits and Misses')
        self.saveTabularInfo(doc)

    # ---*---

    def dataStoreLoad(self):
        gg, doc = ReportGenerationHelper.dataStoreLoad(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'Data Store Disk Load')
        self.saveTabularInfo(doc)

    # ---*---

    def dedupeFactor(self):
        gg, doc = ReportGenerationHelper.dedupeFactor(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        self.render(gg, 'Storage Optimization')
        self.saveTabularInfo(doc)

    # ---*---

    def dnsHits(self):
        gg, doc = ReportGenerationHelper.dnsHits(self.mgmt,
                                                 self.fields,
                                                 ProductGfxContext)
        self.render(gg, 'DNS Cache Hits')
        self.saveTabularInfo(doc)

    # ---*---

    def dnsUtilBytes(self):
        gg, doc = ReportGenerationHelper.dnsUtilBytes(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        self.render(gg, 'DNS Cache Memory Utilization')
        self.saveTabularInfo(doc)

    # ---*---

    def dnsUtilEntries(self):
        gg, doc = ReportGenerationHelper.dnsUtilEntries(self.mgmt,
                                                        self.fields,
                                                        ProductGfxContext)
        self.render(gg, 'DNS Cache Entries')
        self.saveTabularInfo(doc)

    # ---*---

    def csaThroughputFrontEndIn(self):
        gg, doc = ReportGenerationHelper.csaThroughputFrontEndIn(self.mgmt,
                                                                 self.fields,
                                                                 ProductGfxContext)
        self.render(gg, 'Front-End Throughput In')
        self.saveTabularInfo(doc)

    # ---*---

    def csaThroughputFrontEndOut(self):
        gg, doc = ReportGenerationHelper.csaThroughputFrontEndOut(self.mgmt,
                                                                  self.fields,
                                                                  ProductGfxContext)
        self.render(gg, 'Front-End Throughput Out')
        self.saveTabularInfo(doc)

    # ---*---

    def csaThroughputBackEndIn(self):
        gg, doc = ReportGenerationHelper.csaThroughputBackEndIn(self.mgmt,
                                                                self.fields,
                                                                ProductGfxContext)
        self.render(gg, 'Back-End Throughput In')
        self.saveTabularInfo(doc)

    # ---*---

    def csaThroughputBackEndOut(self):
        gg, doc = ReportGenerationHelper.csaThroughputBackEndOut(self.mgmt,
                                                                 self.fields,
                                                                 ProductGfxContext)
        self.render(gg, 'Back-End Throughput Out')
        self.saveTabularInfo(doc)

    # ---*---

    def csaEvictionBytes(self):
        gg, doc = ReportGenerationHelper.csaEvictionBytes(self.mgmt,
                                             self.fields,
                                             ProductGfxContext)
        self.render(gg, 'Evicted Bytes')
        self.saveTabularInfo(doc)

    # ---*---

    def csaEvictionAge(self):
        gg, doc = ReportGenerationHelper.csaEvictionAge(self.mgmt,
                                                        self.fields,
                                                        ProductGfxContext)
        self.render(gg, 'Data Cache Eviction Age')
        self.saveTabularInfo(doc)

    # ---*---

    def csaBytesPending(self):
        gg, doc = ReportGenerationHelper.csaBytesPending(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        self.render(gg, 'Replication Bytes Pending')
        self.saveTabularInfo(doc)

    # ---*---

    def csaDiskThroughput(self):
        fields = self.fields
        gg, doc = ReportGenerationHelper.csaDiskThroughput(self.mgmt,
                                                           self.fields,
                                                           ProductGfxContext)
        disk = fields.get('disk')
        render_str = 'Disk Throughput for ' + disk
        self.render(gg, render_str)
        self.saveTabularInfo(doc)

    # ---*---

    def csaDiskIOPS(self):
        fields = self.fields
        gg, doc = ReportGenerationHelper.csaDiskIOPS(self.mgmt,
                                                     self.fields,
                                                     ProductGfxContext)
        disk = fields.get('disk')
        render_str = 'Disk IOPS for ' + disk
        self.render(gg, render_str)
        self.saveTabularInfo(doc)


    # ---*---

    def csaDiskPercUtil(self):
        fields = self.fields
        gg, doc = ReportGenerationHelper.csaDiskPercUtil(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        disk = fields.get('disk')
        render_str = 'Disk Percentage Utilization for ' + disk
        self.render(gg, render_str)
        self.saveTabularInfo(doc)

    # ---*---

    def csaDiskAqsz(self):
        fields = self.fields
        gg, doc = ReportGenerationHelper.csaDiskAqsz(self.mgmt,
                                                     self.fields,
                                                     ProductGfxContext)
        disk = fields.get('disk')
        render_str = 'Disk Average Queue Size for ' + disk
        self.render(gg, render_str)
        self.saveTabularInfo(doc)

    # ---*---

    def csaDiskAwait(self):
        fields = self.fields
        gg, doc = ReportGenerationHelper.csaDiskAwait(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        disk = fields.get('disk')
        render_str = 'Disk Average Wait for ' + disk
        self.render(gg, render_str)
        self.saveTabularInfo(doc)

    # ---*---

    def csaDiskSvctm(self):
        fields = self.fields
        gg, doc = ReportGenerationHelper.csaDiskSvctm(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        disk = fields.get('disk')
        render_str = 'Disk Average Service Time for ' + disk
        self.render(gg, render_str)
        self.saveTabularInfo(doc)

    # ---*---

    def endpointHistory(self):
        gg, doc = ReportGenerationHelper.endpointHistory(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        self.render(gg, 'Endpoint History')
        self.saveTabularInfo(doc)

    # ---*---

    def evaInitiatorStatsIO(self):
        gg, doc = ReportGenerationHelper.evaInitiatorStatsIO(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext)
        self.render(gg, 'Initiator I/O')
        self.saveTabularInfo(doc)

    # ---*---

    def evaInitiatorStatsIOPS(self):
        gg, doc = ReportGenerationHelper.evaInitiatorStatsIOPS(self.mgmt,
                                                               self.fields,
                                                               ProductGfxContext)
        self.render(gg, 'Initiator I/O Operations Per Second')
        self.saveTabularInfo(doc)

    # ---*---

    def evaInitiatorStatsLatency(self):
        gg, doc = ReportGenerationHelper.evaInitiatorStatsLatency(self.mgmt,
                                                                  self.fields,
                                                                  ProductGfxContext)
        self.render(gg, 'Initiator I/O Latency')
        self.saveTabularInfo(doc)

    # ---*---

    def evaLunStatsIO(self):
        gg, doc = ReportGenerationHelper.evaLunStatsIO(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'LUN I/O')
        self.saveTabularInfo(doc)

    # ---*---

    def evaLunStatsIOPS(self):
        gg, doc = ReportGenerationHelper.evaLunStatsIOPS(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        self.render(gg, 'LUN I/O Operations Per Second')
        self.saveTabularInfo(doc)

    # ---*---

    def evaLunStatsLatency(self):
        gg, doc = ReportGenerationHelper.evaLunStatsLatency(self.mgmt,
                                                            self.fields,
                                                            ProductGfxContext)
        self.render(gg, 'LUN I/O Latency')
        self.saveTabularInfo(doc)

    # ---*---

    def evaBlockstoreStatsHitMiss(self):
        gg, doc = ReportGenerationHelper.evaBlockstoreStatsHitMiss(self.mgmt,
                                                            self.fields,
                                                            ProductGfxContext)
        self.render(gg, 'Blockstore Read Hits / Misses')
        self.saveTabularInfo(doc)

    # ---*---

    def evaBlockstoreStatsUncmtd(self):
        gg, doc = ReportGenerationHelper.evaBlockstoreStatsUncmtd(self.mgmt,
                                                           self.fields,
                                                           ProductGfxContext)
        self.render(gg, 'Data Writes / Commits')
        self.saveTabularInfo(doc)

    # ---*---

    def evaBlockstoreStatsCommitDelay(self):
        gg, doc = ReportGenerationHelper.evaBlockstoreStatsCommitDelay(self.mgmt,
                                                           self.fields,
                                                           ProductGfxContext)
        self.render(gg, 'Commit Delay')
        self.saveTabularInfo(doc)

    # ---*---

    def evaBlockstoreStatsCommitIO(self):
        gg, doc = ReportGenerationHelper.evaBlockstoreStatsCommitIO(self.mgmt,
                                                           self.fields,
                                                           ProductGfxContext)
        self.render(gg, 'Commit Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    def evaNetworkStats(self):
        gg, doc = ReportGenerationHelper.evaNetworkStats(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        self.render(gg, 'Network I/O')
        self.saveTabularInfo(doc)

    # ---*---

    def httpPrefetchPerf(self):
        # Samoa+ only report (for CMC)
        self.httpPrefetchPerfByMode('sc3')

    def httpPrefetchPerfCombined(self):
        # Combined report (for SH)
        self.httpPrefetchPerfByMode('sc2+3')

    def httpPrefetchPerfByMode(self, mode):
        gg, doc = ReportGenerationHelper.httpPrefetchPerfByMode(self.mgmt,
                                                                self.fields,
                                                                mode,
                                                                ProductGfxContext)
        self.render(gg, 'HTTP Total Hits Composition')
        self.saveTabularInfo(doc)

    # ---*---

    def memoryPaging(self):
        gg, doc = ReportGenerationHelper.memoryPaging(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        self.render(gg, 'Memory Paging')
        self.saveTabularInfo(doc)

    # ---*---

    def neighborData(self):
        gg, doc = ReportGenerationHelper.neighborData(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        self.render(gg, 'Connection Forwarding IO')
        self.saveTabularInfo(doc)

    # ---*---

    def nfsCalls(self):
        gg, doc = ReportGenerationHelper.nfsCalls(self.mgmt,
                                                  self.fields,
                                                  ProductGfxContext)
        self.render(gg, 'NFS Calls')
        self.saveTabularInfo(doc)

    # ---*---

    def pfsData(self):
        gg, doc = ReportGenerationHelper.pfsData(self.mgmt,
                                                 self.fields,
                                                 ProductGfxContext)
        self.render(gg, 'PFS Statistics')
        self.saveTabularInfo(doc)

    # ---*---

    def rspVNIIO(self):
        vni = self.fields.get('vni', 'none')
        if not vni or vni == 'none':
            return
        gg, doc = ReportGenerationHelper.rspVNIIO(self.mgmt,
                                                  self.fields,
                                                  ProductGfxContext)

        if RVBDUtils.isSH():
            import rsp
            rspText = '%s VNI IO' % rsp.publicName()
        else:
            rspText = 'RSP VNI IO'

        self.render(gg, rspText)
        self.saveTabularInfo(doc)

    # ---*---

    def rsp3Vni(self):
        gg, doc = ReportGenerationHelper.rsp3Vni(self.mgmt,
                                                 self.fields,
                                                 ProductGfxContext)
        self.render(gg, 'VSP VNI IO')
        self.saveTabularInfo(doc)

    # ---*---

    def qosClassesEnforced(self):
        gg, doc = ReportGenerationHelper.qosClassesEnforced(self.mgmt,
                                                            self.fields,
                                                            ProductGfxContext,
                                                            False,
                                                            session = self.request())
        self.render(gg, 'Outbound QoS Class-Enforced')
        self.saveTabularInfo(doc)

    # ---*---

    def qosClassesPreEnforcement(self):
        gg, doc = ReportGenerationHelper.qosClassesPreEnforcement(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext,
                                                             False,
                                                             session = self.request())
        self.render(gg, 'Outbound QoS Pre-Enforcement')
        self.saveTabularInfo(doc)

    # ---*---

    def qosInboundClassesEnforced(self):
        gg, doc = ReportGenerationHelper.qosInboundClassesEnforced(self.mgmt,
                                                            self.fields,
                                                            ProductGfxContext,
                                                            False,
                                                            session = self.request())
        self.render(gg, 'Inbound QoS Class-Enforced')
        self.saveTabularInfo(doc)

    # ---*---

    def qosInboundClassesPreEnforcement(self):
        gg, doc = ReportGenerationHelper.qosInboundClassesPreEnforcement(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext,
                                                             False,
                                                             session = self.request())
        self.render(gg, 'Inbound QoS Pre-Enforcement')
        self.saveTabularInfo(doc)

    # ---*---

    def srdfOverviewLan(self):
        gg, doc = ReportGenerationHelper.srdfOverviewLan(self.mgmt,
                                                    self.fields,
                                                    ProductGfxContext)
        self.render(gg, 'SRDF LAN Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    def srdfOverviewWan(self):
        gg, doc = ReportGenerationHelper.srdfOverviewWan(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        self.render(gg, 'SRDF WAN Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    def srdfOverviewDataReduction(self):
        gg, doc = ReportGenerationHelper.srdfOverviewDataReduction(self.mgmt,
                                                                   self.fields,
                                                                   ProductGfxContext)
        self.render(gg, 'Data Reduction')
        self.saveTabularInfo(doc)

    # ---*---

    def srdfServerDetailLan(self):
        gg = ReportGenerationHelper.srdfServerDetailLan(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext)
        self.render(gg, 'Symmetrix LAN Throughput')

    # ---*---

    def srdfServerDetailWan(self):
        gg = ReportGenerationHelper.srdfServerDetailWan(self.mgmt,
                                                             self.fields,
                                                             ProductGfxContext)
        self.render(gg, 'Symmetrix WAN Throughput')

    # ---*---

    def srdfServerDetailDataReduction(self):
        gg, doc = ReportGenerationHelper.srdfServerDetailDataReduction(self.mgmt,
                                                                       self.fields,
                                                                       ProductGfxContext)
        self.render(gg, 'Data Reduction')
        self.saveTabularInfo(doc)

    # ---*---

    def srdfGroupDetailThroughput(self):
        gg, doc = ReportGenerationHelper.srdfGroupDetailThroughput(self.mgmt,
                                                              self.fields,
                                                              ProductGfxContext)
        self.render(gg, 'RDF Group Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    def srdfGroupDetailDataReduction(self):
        gg, doc = ReportGenerationHelper.srdfGroupDetailDataReduction(self.mgmt,
                                                              self.fields,
                                                              ProductGfxContext)
        self.render(gg, 'Data Reduction')
        self.saveTabularInfo(doc)

    # ---*---

    def sslConnectionRequests(self):
        gg, doc = ReportGenerationHelper.sslConnectionRequests(self.mgmt,
                                                               self.fields,
                                                               ProductGfxContext)
        self.render(gg, 'SSL Connection Requests')
        self.saveTabularInfo(doc)

    # ---*---

    def sslConnectionRate(self):
        gg, doc = ReportGenerationHelper.sslConnectionRate(self.mgmt,
                                                           self.fields,
                                                           ProductGfxContext)
        self.render(gg, 'SSL Connection Rate')
        self.saveTabularInfo(doc)

    # ---*---

    def sslOptimization(self):
        gg, doc = ReportGenerationHelper.sslOptimization(self.mgmt,
                                                         self.fields,
                                                         ProductGfxContext)
        self.render(gg, 'SSL Optimization')
        self.saveTabularInfo(doc)

    # ---*---

    def throughputLan(self):
        gg, doc = ReportGenerationHelper.throughputLan(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'Optimized LAN Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    def throughputWan(self):
        gg, doc = ReportGenerationHelper.throughputWan(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'Optimized WAN Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    # 3D Traffic Overview report
    def bandwidthSummary(self):
        gg, doc = ReportGenerationHelper.bandwidthSummary(self.mgmt,
                                                          self.fields,
                                                          ProductGfxContext)
        self.render(gg, 'Bandwidth Summary')

    # ---*---

    # traffic summary pie chart
    def trafficSummary(self):
        gg, doc = ReportGenerationHelper.trafficSummary(self.mgmt,
                                                        self.fields,
                                                        ProductGfxContext)
        self.render(gg, 'Traffic Summary')
        self.saveTabularInfo(doc)

    # ---*---

    def rsp3VmCpuUtil(self):
        gg, doc = ReportGenerationHelper.rsp3VmCpuUtil(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'VM CPU Utilization')
        self.saveTabularInfo(doc)

    # ---*---

    def rsp3VmMemory(self):
        gg, doc = ReportGenerationHelper.rsp3VmMemory(self.mgmt,
                                                      self.fields,
                                                      ProductGfxContext)
        self.render(gg, 'VM Memory Usage')
        self.saveTabularInfo(doc)

    # ---*---

    def rsp3VmDiskOps(self):
        gg, doc = ReportGenerationHelper.rsp3VmDiskOps(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'VM Disk IO')
        self.saveTabularInfo(doc)

    # ---*---

    def rsp3VmDiskTput(self):
        gg, doc = ReportGenerationHelper.rsp3VmDiskTput(self.mgmt,
                                                        self.fields,
                                                        ProductGfxContext)
        self.render(gg, 'VM Disk Throughput')
        self.saveTabularInfo(doc)

    # ---*---

    def hypervisorCpu(self):
        gg, doc = ReportGenerationHelper.hypervisorCpu(self.mgmt,
                                                       self.fields,
                                                       ProductGfxContext)
        self.render(gg, 'Hypervisor CPU Utilization')
        self.saveTabularInfo(doc)

    # ---*---

    def hypervisorMemory(self):
        gg, doc = ReportGenerationHelper.hypervisorMemory(self.mgmt,
                                                          self.fields,
                                                          ProductGfxContext)
        self.render(gg, 'Hypervisor Memory Usage')
        self.saveTabularInfo(doc)

    # ---*---

    def tcpMemoryConsumption(self):
        gg, doc = ReportGenerationHelper.tcpMemoryConsumption(self.mgmt,
                                                              self.fields,
                                                              ProductGfxContext)
        self.render(gg, 'TCP Memory Consumption')
        self.saveTabularInfo(doc)

    # ---*---

    def tcpMemoryPressure(self):
        gg, doc = ReportGenerationHelper.tcpMemoryPressure(self.mgmt,
                                                           self.fields,
                                                           ProductGfxContext)
        self.render(gg, 'Time Spent in TCP Memory Pressure')
        self.saveTabularInfo(doc)
