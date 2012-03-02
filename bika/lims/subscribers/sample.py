from DateTime import DateTime
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.WorkflowCore import WorkflowException
from bika.lims import logger

def AfterTransitionEventHandler(sample, event):

    # creation doesn't have a 'transition'
    if not event.transition:
        return

    if not sample.REQUEST.has_key('workflow_skiplist'):
        sample.REQUEST['workflow_skiplist'] = [sample.UID(), ]
    else:
        if sample.UID() in sample.REQUEST['workflow_skiplist']:
            logger.info("SM Skip")
            return
        else:
            sample.REQUEST["workflow_skiplist"].append(sample.UID())

    logger.info("Starting: %s on %s" % (event.transition.id, sample))

    workflow = getToolByName(sample, 'portal_workflow')
    parts = sample.objectValues('SamplePartition')

    if event.transition.id == "receive":
        if sample.getDateSampled() > DateTime():
            raise WorkflowException
        sample.setDateReceived(DateTime())
        sample.reindexObject(idxs = ["review_state", "getDateReceived", ])

        # Receive all sample partitions that are still 'due'
        due = [sp for sp in parts \
               if workflow.getInfoFor(sp, 'review_state') == 'due']
        for sp in due:
            workflow.doActionFor(sp, 'receive')

        # when a sample is received, all associated
        # AnalysisRequests are also transitioned
        for ar in sample.getAnalysisRequests():
            if not ar.UID() in sample.REQUEST['workflow_skiplist']:
                workflow.doActionFor(ar, "receive")

    elif event.transition.id == "expire":
        sample.setDateExpired(DateTime())
        sample.reindexObject(idxs = ["review_state", "getDateExpired", ])

    #---------------------
    # Secondary workflows:
    #---------------------

    elif event.transition.id == "reinstate":
        sample.reindexObject(idxs = ["cancellation_state", ])

        # Re-instate all sample partitions
        for sp in [sp for sp in parts
                   if workflow.getInfoFor(sp, 'cancellation_state') == 'cancelled']:
            workflow.doActionFor(sp, 'reinstate')

        # reinstate all ARs for this sample.
        ars = sample.getAnalysisRequests()
        for ar in ars:
            if not ar.UID in sample.REQUEST['workflow_skiplist']:
                ar_state = workflow.getInfoFor(ar, 'cancellation_state')
                if ar_state == 'cancelled':
                    workflow.doActionFor(ar, 'reinstate')

    elif event.transition.id == "cancel":
        sample.reindexObject(idxs = ["cancellation_state", ])

        # Cancel all partitions
        for sp in [sp for sp in parts
                   if workflow.getInfoFor(sp, 'cancellation_state') == 'active']:
            workflow.doActionFor(sp, 'cancel')

        # cancel all ARs for this sample.
        ars = sample.getAnalysisRequests()
        for ar in ars:
            if not ar.UID in sample.REQUEST['workflow_skiplist']:
                ar_state = workflow.getInfoFor(ar, 'cancellation_state')
                if ar_state == 'active':
                    workflow.doActionFor(ar, 'cancel')

    return
